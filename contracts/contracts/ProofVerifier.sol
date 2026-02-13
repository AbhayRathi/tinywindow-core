// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ProofVerifier
 * @dev Contract for verifying cryptographic proofs of trading decisions
 */
contract ProofVerifier {
    struct Proof {
        bytes32 proofHash;
        bytes32 decisionHash;
        bytes signature;
        address signer;
        uint256 timestamp;
        bool valid;
    }

    // Mapping from proof ID to Proof
    mapping(bytes32 => Proof) public proofs;
    
    // Mapping of authorized signers
    mapping(address => bool) public authorizedSigners;
    
    // Owner address
    address public owner;

    // Events
    event ProofSubmitted(
        bytes32 indexed proofId,
        bytes32 indexed decisionHash,
        address indexed signer,
        uint256 timestamp
    );
    
    event ProofValidated(
        bytes32 indexed proofId,
        bool valid,
        uint256 timestamp
    );
    
    event SignerAuthorized(
        address indexed signer,
        uint256 timestamp
    );
    
    event SignerRevoked(
        address indexed signer,
        uint256 timestamp
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedSigners[msg.sender] = true;
    }

    /**
     * @dev Submit a proof for verification
     * @param decisionHash Hash of the trading decision
     * @param signature Cryptographic signature
     */
    function submitProof(
        bytes32 decisionHash,
        bytes memory signature
    ) external returns (bytes32) {
        bytes32 proofHash = keccak256(
            abi.encodePacked(decisionHash, signature)
        );
        
        bytes32 proofId = keccak256(
            abi.encodePacked(proofHash, msg.sender, block.timestamp)
        );

        require(
            proofs[proofId].timestamp == 0,
            "Proof already submitted"
        );

        proofs[proofId] = Proof({
            proofHash: proofHash,
            decisionHash: decisionHash,
            signature: signature,
            signer: msg.sender,
            timestamp: block.timestamp,
            valid: false
        });

        emit ProofSubmitted(
            proofId,
            decisionHash,
            msg.sender,
            block.timestamp
        );

        return proofId;
    }

    /**
     * @dev Validate a proof (simplified verification)
     * @param proofId ID of the proof to validate
     * @param expectedSigner Expected signer address
     */
    function validateProof(
        bytes32 proofId,
        address expectedSigner
    ) external onlyOwner {
        require(
            proofs[proofId].timestamp != 0,
            "Proof not found"
        );

        require(
            authorizedSigners[expectedSigner],
            "Signer not authorized"
        );

        // In a real implementation, this would perform actual signature verification
        // For now, we just check if the signer matches
        bool valid = (proofs[proofId].signer == expectedSigner);

        proofs[proofId].valid = valid;

        emit ProofValidated(
            proofId,
            valid,
            block.timestamp
        );
    }

    /**
     * @dev Authorize a signer
     * @param signer Address to authorize
     */
    function authorizeSigner(address signer) external onlyOwner {
        require(!authorizedSigners[signer], "Signer already authorized");
        authorizedSigners[signer] = true;
        
        emit SignerAuthorized(signer, block.timestamp);
    }

    /**
     * @dev Revoke a signer's authorization
     * @param signer Address to revoke
     */
    function revokeSigner(address signer) external onlyOwner {
        require(authorizedSigners[signer], "Signer not authorized");
        require(signer != owner, "Cannot revoke owner");
        authorizedSigners[signer] = false;
        
        emit SignerRevoked(signer, block.timestamp);
    }

    /**
     * @dev Check if a proof is valid
     * @param proofId ID of the proof
     */
    function isProofValid(bytes32 proofId) external view returns (bool) {
        return proofs[proofId].valid;
    }

    /**
     * @dev Get proof details
     * @param proofId ID of the proof
     */
    function getProof(bytes32 proofId)
        external
        view
        returns (
            bytes32 proofHash,
            bytes32 decisionHash,
            bytes memory signature,
            address signer,
            uint256 timestamp,
            bool valid
        )
    {
        Proof memory proof = proofs[proofId];
        return (
            proof.proofHash,
            proof.decisionHash,
            proof.signature,
            proof.signer,
            proof.timestamp,
            proof.valid
        );
    }

    /**
     * @dev Transfer ownership
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid new owner");
        owner = newOwner;
        authorizedSigners[newOwner] = true;
    }
}
