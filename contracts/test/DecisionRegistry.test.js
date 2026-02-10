const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DecisionRegistry", function () {
  let decisionRegistry, owner, agent1, agent2;

  beforeEach(async function () {
    [owner, agent1, agent2] = await ethers.getSigners();
    const DecisionRegistry = await ethers.getContractFactory("DecisionRegistry");
    decisionRegistry = await DecisionRegistry.deploy();
    await proofVerifier.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should set the right owner", async function () {
      expect(await decisionRegistry.owner()).to.equal(owner.address);
    });
  });

  describe("Decision Recording", function () {
    it("Should record a decision", async function () {
      const hash = ethers.id("decision-hash");
      const sig = ethers.toUtf8Bytes("signature");
      await expect(decisionRegistry.recordDecision(hash, sig, "BTC/USD", "BUY"))
        .to.emit(decisionRegistry, "DecisionRecorded");
    });

    it("Should retrieve decision by ID", async function () {
      const hash = ethers.id("decision-hash");
      const sig = ethers.toUtf8Bytes("signature");
      const tx = await decisionRegistry.recordDecision(hash, sig, "BTC/USD", "BUY");
      const receipt = await tx.wait();
      const event = receipt.logs.find(log => log.fragment && log.fragment.name === "DecisionRecorded");
      const decisionId = event.args[0];
      const decision = await decisionRegistry.getDecision(decisionId);
      expect(decision.symbol).to.equal("BTC/USD");
      expect(decision.action).to.equal("BUY");
    });
  });

  describe("Decision Verification", function () {
    it("Should verify a decision", async function () {
      const hash = ethers.id("decision-hash");
      const sig = ethers.toUtf8Bytes("signature");
      const tx = await decisionRegistry.recordDecision(hash, sig, "BTC/USD", "BUY");
      const receipt = await tx.wait();
      const event = receipt.logs.find(log => log.fragment && log.fragment.name === "DecisionRecorded");
      const decisionId = event.args[0];
      await decisionRegistry.verifyDecision(decisionId);
      const decision = await decisionRegistry.getDecision(decisionId);
      expect(decision.verified).to.be.true;
    });
  });
});
