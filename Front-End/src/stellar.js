import { Horizon, Networks, TransactionBuilder, Operation, Asset, BASE_FEE, StrKey } from '@stellar/stellar-sdk';
import { isConnected, requestAccess, getNetworkDetails, signTransaction } from '@stellar/freighter-api';

const server = new Horizon.Server('https://horizon-testnet.stellar.org');
export const issuer = import.meta.env.VITE_HRW_ISSUER || '';
export async function connectWallet() {
  const connection = await isConnected();
  if (!connection.isConnected) throw new Error('Install the Freighter browser extension, unlock it, and select Testnet.');
  const access = await requestAccess();
  if (access.error || !access.address) throw new Error(access.error?.message || 'Wallet connection was declined.');
  const network = await getNetworkDetails();
  if (network.networkPassphrase !== Networks.TESTNET) throw new Error('Switch Freighter to Stellar Testnet, then connect again.');
  return access.address;
}
export async function readWallet(address) {
  try {
    const account = await server.loadAccount(address);
    const payments = await server.payments().forAccount(address).order('desc').limit(6).call();
    return { balances: account.balances, payments: payments.records, funded: true };
  } catch (error) {
    if (error.response?.status === 404) return { balances: [], payments: [], funded: false };
    throw error;
  }
}
export async function fundWallet(address) {
  const response = await fetch(`https://friendbot.stellar.org?addr=${encodeURIComponent(address)}`);
  if (!response.ok) throw new Error('Friendbot could not fund this account. It may already be funded; try refreshing.');
}
export async function addTrustline(address) {
  if (!StrKey.isValidEd25519PublicKey(issuer)) throw new Error('Configure a valid VITE_HRW_ISSUER public address in .env first.');
  const network = await getNetworkDetails();
  if (network.networkPassphrase !== Networks.TESTNET) throw new Error('Select Testnet in Freighter before signing.');
  const account = await server.loadAccount(address);
  const transaction = new TransactionBuilder(account, { fee: BASE_FEE, networkPassphrase: Networks.TESTNET })
    .addOperation(Operation.changeTrust({ asset: new Asset('HRW', issuer) })).setTimeout(120).build();
  const signed = await signTransaction(transaction.toXDR(), { networkPassphrase: Networks.TESTNET, address });
  if (signed.error || !signed.signedTxXdr) throw new Error(signed.error?.message || 'Transaction signing was declined.');
  return server.submitTransaction(TransactionBuilder.fromXDR(signed.signedTxXdr, Networks.TESTNET));
}
