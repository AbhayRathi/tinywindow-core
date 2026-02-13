const hre = require("hardhat");

async function main() {
  console.log("Deploying TinyWindow contracts...");

  // Deploy ProofVerifier
  const ProofVerifier = await hre.ethers.getContractFactory("ProofVerifier");
  const proofVerifier = await ProofVerifier.deploy();
  await proofVerifier.waitForDeployment();
  console.log(`ProofVerifier deployed to: ${await proofVerifier.getAddress()}`);

  // Deploy DecisionRegistry
  const DecisionRegistry = await hre.ethers.getContractFactory("DecisionRegistry");
  const decisionRegistry = await DecisionRegistry.deploy();
  await decisionRegistry.waitForDeployment();
  console.log(`DecisionRegistry deployed to: ${await decisionRegistry.getAddress()}`);

  console.log("\nDeployment complete!");
  console.log("\nContract addresses:");
  console.log("- ProofVerifier:", await proofVerifier.getAddress());
  console.log("- DecisionRegistry:", await decisionRegistry.getAddress());
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
