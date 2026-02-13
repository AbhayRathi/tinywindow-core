const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ProofVerifier", function () {
  let proofVerifier, owner, signer1, signer2;

  beforeEach(async function () {
    [owner, signer1, signer2] = await ethers.getSigners();
    const ProofVerifier = await ethers.getContractFactory("ProofVerifier");
    proofVerifier = await ProofVerifier.deploy();
    await proofVerifier.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should set the right owner", async function () {
      expect(await proofVerifier.owner()).to.equal(owner.address);
    });

    it("Should authorize owner as signer", async function () {
      expect(await proofVerifier.authorizedSigners(owner.address)).to.be.true;
    });
  });

  describe("Proof Submission", function () {
    it("Should submit a proof successfully", async function () {
      const decisionHash = ethers.id("test-decision");
      const signature = ethers.toUtf8Bytes("test-signature");
      await expect(proofVerifier.submitProof(decisionHash, signature))
        .to.emit(proofVerifier, "ProofSubmitted");
    });

    it("Should store proof data correctly", async function () {
      const decisionHash = ethers.id("test-decision");
      const signature = ethers.toUtf8Bytes("test-signature");
      const tx = await proofVerifier.submitProof(decisionHash, signature);
      const receipt = await tx.wait();
      const event = receipt.logs.find(log => log.fragment && log.fragment.name === "ProofSubmitted");
      const proofId = event.args[0];
      const proof = await proofVerifier.getProof(proofId);
      expect(proof.decisionHash).to.equal(decisionHash);
      expect(proof.signer).to.equal(owner.address);
      expect(proof.valid).to.be.false;
    });
  });

  describe("Signer Management", function () {
    it("Should authorize a new signer", async function () {
      await proofVerifier.authorizeSigner(signer1.address);
      expect(await proofVerifier.authorizedSigners(signer1.address)).to.be.true;
    });

    it("Should revoke a signer", async function () {
      await proofVerifier.authorizeSigner(signer1.address);
      await proofVerifier.revokeSigner(signer1.address);
      expect(await proofVerifier.authorizedSigners(signer1.address)).to.be.false;
    });

    it("Should not revoke owner", async function () {
      await expect(proofVerifier.revokeSigner(owner.address))
        .to.be.revertedWith("Cannot revoke owner");
    });
  });
});
