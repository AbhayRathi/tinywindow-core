// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title DecisionRegistry
 * @dev Registry for storing cryptographic proofs of trading decisions
 */
contract DecisionRegistry is Ownable {
    struct Decision {
        bytes32 decisionHash;
        bytes signature;
        address agent;
        uint256 timestamp;
        string symbol;
        string action;
        bool verified;
    }

    // Mapping from decision ID to Decision
    mapping(bytes32 => Decision) public decisions;
    
    // Array of all decision IDs for enumeration
    bytes32[] public decisionIds;
    
    // Mapping from agent address to their decision IDs
    mapping(address => bytes32[]) public agentDecisions;

    // Events
    event DecisionRecorded(
        bytes32 indexed decisionId,
        address indexed agent,
        string symbol,
        string action,
        uint256 timestamp
    );
    
    event DecisionVerified(
        bytes32 indexed decisionId,
        address indexed verifier,
        uint256 timestamp
    );

    constructor() Ownable(msg.sender) {}

    /**
     * @dev Record a new trading decision with proof
     * @param decisionHash Hash of the decision data
     * @param signature Cryptographic signature
     * @param symbol Trading pair symbol
     * @param action Trading action (BUY, SELL, HOLD)
     */
    function recordDecision(
        bytes32 decisionHash,
        bytes memory signature,
        string memory symbol,
        string memory action
    ) external returns (bytes32) {
        bytes32 decisionId = keccak256(
            abi.encodePacked(decisionHash, msg.sender, block.timestamp)
        );

        require(
            decisions[decisionId].timestamp == 0,
            "Decision already recorded"
        );

        decisions[decisionId] = Decision({
            decisionHash: decisionHash,
            signature: signature,
            agent: msg.sender,
            timestamp: block.timestamp,
            symbol: symbol,
            action: action,
            verified: false
        });

        decisionIds.push(decisionId);
        agentDecisions[msg.sender].push(decisionId);

        emit DecisionRecorded(
            decisionId,
            msg.sender,
            symbol,
            action,
            block.timestamp
        );

        return decisionId;
    }

    /**
     * @dev Verify a decision (only owner or authorized verifier)
     * @param decisionId ID of the decision to verify
     */
    function verifyDecision(bytes32 decisionId) external onlyOwner {
        require(
            decisions[decisionId].timestamp != 0,
            "Decision not found"
        );
        require(
            !decisions[decisionId].verified,
            "Decision already verified"
        );

        decisions[decisionId].verified = true;

        emit DecisionVerified(
            decisionId,
            msg.sender,
            block.timestamp
        );
    }

    /**
     * @dev Get decision details
     * @param decisionId ID of the decision
     */
    function getDecision(bytes32 decisionId)
        external
        view
        returns (
            bytes32 decisionHash,
            bytes memory signature,
            address agent,
            uint256 timestamp,
            string memory symbol,
            string memory action,
            bool verified
        )
    {
        Decision memory decision = decisions[decisionId];
        return (
            decision.decisionHash,
            decision.signature,
            decision.agent,
            decision.timestamp,
            decision.symbol,
            decision.action,
            decision.verified
        );
    }

    /**
     * @dev Get all decisions for an agent
     * @param agent Address of the agent
     */
    function getAgentDecisions(address agent)
        external
        view
        returns (bytes32[] memory)
    {
        return agentDecisions[agent];
    }

    /**
     * @dev Get total number of decisions
     */
    function getDecisionCount() external view returns (uint256) {
        return decisionIds.length;
    }

    /**
     * @dev Get decision ID by index
     * @param index Index in the decisionIds array
     */
    function getDecisionIdByIndex(uint256 index)
        external
        view
        returns (bytes32)
    {
        require(index < decisionIds.length, "Index out of bounds");
        return decisionIds[index];
    }
}
