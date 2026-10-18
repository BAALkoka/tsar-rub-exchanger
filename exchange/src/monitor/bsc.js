// src/monitor/bsc.js — watcher skeleton for BSC (ethers.js)

const { ethers } = require('ethers');
require('dotenv').config();

const rpc = process.env.BSC_RPC;
const provider = new ethers.JsonRpcProvider(rpc);

const TOKEN_ADDRESS = process.env.CSARY_TOKEN_CONTRACT_BSC; // BEP-20

const ABI = [
  // minimal ERC20 Transfer event
  "event Transfer(address indexed from, address indexed to, uint256 value)",
];

const token = new ethers.Contract(TOKEN_ADDRESS, ABI, provider);

function start() {
  console.log('BSC watcher starting for', TOKEN_ADDRESS);
  token.on('Transfer', (from, to, value, event) => {
    // Implement: detect deposits to monitored addresses (deposit aggregator or per-user)
    console.log('Transfer', { from, to, value: value.toString() });
    // Call backend webhook to record deposit
  });
}

module.exports = { start };
