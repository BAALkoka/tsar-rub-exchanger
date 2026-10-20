const { ethers } = require('ethers');
require('dotenv').config();

const rpc = process.env.BSC_RPC;
if (!rpc) {
  console.error('BSC_RPC is not set. Set it in env before starting monitor.');
  process.exit(1);
}

const provider = new ethers.JsonRpcProvider(rpc);
const tokenAddress = process.env.CSARY_TOKEN_CONTRACT_BSC;

if (!tokenAddress) {
  console.error('CSARY_TOKEN_CONTRACT_BSC is not set.');
  process.exit(1);
}

const ABI = [
  'event Transfer(address indexed from, address indexed to, uint256 value)'
];

const token = new ethers.Contract(tokenAddress, ABI, provider);

function start() {
  console.log('BSC monitor is starting for token:', tokenAddress);
  token.on('Transfer', async (from, to, value, event) => {
    const payload = {
      txHash: event.transactionHash,
      network: 'BSC',
      toAddress: to,
      amountTokens: ethers.formatUnits(value, 0),
      userId: process.env.DEFAULT_USER_ID || 'system',
      from,
    };

    console.log('Detected Transfer:', payload);

    if (process.env.API_URL) {
      try {
        const response = await fetch(`${process.env.API_URL}/api/webhook/deposit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const text = await response.text();
        console.log('Webhook response:', response.status, text);
      } catch (err) {
        console.error('Failed to send webhook', err);
      }
    }
  });
}

start();
