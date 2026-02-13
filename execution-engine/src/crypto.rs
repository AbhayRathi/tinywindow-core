use ed25519_dalek::{
    Signature as Ed25519Signature, Signer, SigningKey as Ed25519SigningKey, Verifier, VerifyingKey,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::{Error, Result};

/// Wrapper around Ed25519 signing key
#[derive(Clone)]
pub struct SigningKey {
    inner: Ed25519SigningKey,
}

impl SigningKey {
    /// Generate a new random signing key
    pub fn generate() -> Self {
        use rand::RngCore;
        let mut csprng = rand::rngs::OsRng;
        let mut secret_bytes = [0u8; 32];
        csprng.fill_bytes(&mut secret_bytes);
        Self {
            inner: Ed25519SigningKey::from_bytes(&secret_bytes),
        }
    }

    /// Create from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        let inner = Ed25519SigningKey::from_bytes(
            bytes
                .try_into()
                .map_err(|_| Error::Crypto("Invalid key length".to_string()))?,
        );
        Ok(Self { inner })
    }

    /// Get the verification key
    pub fn verification_key(&self) -> VerificationKey {
        VerificationKey {
            inner: self.inner.verifying_key(),
        }
    }

    /// Sign data
    pub fn sign(&self, data: &[u8]) -> Signature {
        let signature = self.inner.sign(data);
        Signature { inner: signature }
    }

    /// Export as bytes
    pub fn to_bytes(&self) -> [u8; 32] {
        self.inner.to_bytes()
    }
}

/// Wrapper around Ed25519 verification key
#[derive(Clone, Serialize, Deserialize)]
pub struct VerificationKey {
    #[serde(
        serialize_with = "serialize_bytes",
        deserialize_with = "deserialize_bytes"
    )]
    inner: VerifyingKey,
}

fn serialize_bytes<S>(key: &VerifyingKey, serializer: S) -> std::result::Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    serializer.serialize_str(&hex::encode(key.to_bytes()))
}

fn deserialize_bytes<'de, D>(deserializer: D) -> std::result::Result<VerifyingKey, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    let bytes = hex::decode(&s).map_err(serde::de::Error::custom)?;
    let bytes: [u8; 32] = bytes
        .try_into()
        .map_err(|_| serde::de::Error::custom("Invalid key length"))?;
    VerifyingKey::from_bytes(&bytes).map_err(serde::de::Error::custom)
}

impl VerificationKey {
    /// Verify a signature
    pub fn verify(&self, data: &[u8], signature: &Signature) -> Result<()> {
        self.inner
            .verify(data, &signature.inner)
            .map_err(|e| Error::Crypto(format!("Signature verification failed: {}", e)))
    }

    /// Export as bytes
    pub fn to_bytes(&self) -> [u8; 32] {
        self.inner.to_bytes()
    }

    /// Import from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        let inner = VerifyingKey::from_bytes(
            bytes
                .try_into()
                .map_err(|_| Error::Crypto("Invalid key length".to_string()))?,
        )
        .map_err(|e| Error::Crypto(format!("Invalid verification key: {}", e)))?;
        Ok(Self { inner })
    }
}

/// Wrapper around Ed25519 signature
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signature {
    #[serde(serialize_with = "serialize_sig", deserialize_with = "deserialize_sig")]
    inner: Ed25519Signature,
}

fn serialize_sig<S>(sig: &Ed25519Signature, serializer: S) -> std::result::Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    serializer.serialize_str(&hex::encode(sig.to_bytes()))
}

fn deserialize_sig<'de, D>(deserializer: D) -> std::result::Result<Ed25519Signature, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    let bytes = hex::decode(&s).map_err(serde::de::Error::custom)?;
    let bytes: [u8; 64] = bytes
        .try_into()
        .map_err(|_| serde::de::Error::custom("Invalid signature length"))?;
    Ok(Ed25519Signature::from_bytes(&bytes))
}

impl Signature {
    /// Export as bytes
    pub fn to_bytes(&self) -> [u8; 64] {
        self.inner.to_bytes()
    }

    /// Import from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        let inner = Ed25519Signature::from_bytes(
            bytes
                .try_into()
                .map_err(|_| Error::Crypto("Invalid signature length".to_string()))?,
        );
        Ok(Self { inner })
    }
}

/// Hash data using SHA-256
pub fn hash_data(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sign_and_verify() {
        let key = SigningKey::generate();
        let data = b"test message";

        let signature = key.sign(data);
        let verification_key = key.verification_key();

        assert!(verification_key.verify(data, &signature).is_ok());
    }

    #[test]
    fn test_verify_fails_with_wrong_data() {
        let key = SigningKey::generate();
        let data = b"test message";
        let wrong_data = b"wrong message";

        let signature = key.sign(data);
        let verification_key = key.verification_key();

        assert!(verification_key.verify(wrong_data, &signature).is_err());
    }

    #[test]
    fn test_hash_consistency() {
        let data = b"test data";
        let hash1 = hash_data(data);
        let hash2 = hash_data(data);

        assert_eq!(hash1, hash2);
    }
}
