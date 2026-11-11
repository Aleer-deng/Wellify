# Wellify

Wellify is a digital health and wellness incentive application. Users track physical activity, set goals, earn wellness points and redeem rewards through a React frontend and Django backend.

## Stellar integration

**Wellify integrates Stellar Testnet through a Freighter wallet and the HRW asset.** Open **My wallet** in the application to connect Freighter, view on-chain balances and recent payment activity, fund a Testnet account, and enable HRW by signing a trustline transaction.

### Where Stellar is integrated

| Integration | What it does | Implementation |
| --- | --- | --- |
| Freighter wallet connection | Requests a public wallet address and checks that Freighter is on Stellar Testnet. | [`connectWallet()` in Front-End/src/stellar.js](Front-End/src/stellar.js) |
| Stellar Horizon account data | Reads XLM and asset balances plus the six most recent payment records from Testnet Horizon. | [`readWallet()` in Front-End/src/stellar.js](Front-End/src/stellar.js) |
| Testnet account funding | Requests test XLM from Stellar Friendbot for the connected account. | [`fundWallet()` in Front-End/src/stellar.js](Front-End/src/stellar.js) |
| HRW asset trustline | Builds a `changeTrust` transaction for the configured HRW issuer, requests signing in Freighter, and submits the signed transaction to Horizon. | [`addTrustline()` in Front-End/src/stellar.js](Front-End/src/stellar.js) |
| Wallet interface | Provides Connect Freighter, Fund with Friendbot, Enable HRW token, balance display, and recent network activity under My wallet. | [Front-End/src/App.jsx](Front-End/src/App.jsx) |
| Backend wallet ownership verification | Issues a five-minute, single-use challenge, verifies an Ed25519 signature with the Python Stellar SDK, and stores the verified wallet address. | [`WalletChallengeView` and `WalletVerifyView` in Back-End/wellness/views.py](Back-End/wellness/views.py) |
| Backend Stellar balance lookup | Retrieves balances for a verified linked wallet through Testnet Horizon. | [`WalletView` in Back-End/wellness/views.py](Back-End/wellness/views.py) |

The frontend uses `@stellar/stellar-sdk` and `@stellar/freighter-api`; the backend uses the Python `stellar-sdk` package. The configured Horizon endpoint is `https://horizon-testnet.stellar.org`.

### Try the Stellar wallet

1. Follow the [frontend setup](Front-End/IMPLEMENTATION.md) and [backend setup](Back-End/readme.md) to run Wellify locally.
2. Install and unlock Freighter, select **Stellar Testnet**, and open **My wallet** in Wellify.
3. Choose **Connect Freighter** and approve access to your public address.
4. For an unfunded account, choose **Fund with Friendbot** to receive test XLM.
5. To enable HRW, set `VITE_HRW_ISSUER` in `Front-End/.env` to the HRW issuer's public address and restart Vite. Choose **Enable HRW token** and approve the trustline transaction in Freighter.
6. Refresh the wallet to view balances and recent network activity. Creating a trustline allows the account to hold HRW; it does not issue tokens or credit an HRW balance.

For backend wallet balance lookups, configure `HRW_ISSUER_PUBLIC_KEY` in `Back-End/.env` to the same issuer public address. The wallet API routes are `POST /api/v1/wallet/challenge/`, `POST /api/v1/wallet/verify/`, and `GET /api/v1/wallet/`. See the [backend documentation](Back-End/readme.md) for the signature format and API details.

### Wellness points and Stellar HRW

**Wellify wellness points are stored in the backend's points ledger and are separate from the on-chain HRW asset.** Approved activities and completed challenges award application points; reward redemptions debit those points. The current implementation does not mint or distribute HRW, execute token payments, or convert wellness points into tokens.

The Freighter connection lasts for the browser session and does not automatically link a verified wallet to the backend account. The backend ownership challenge is a custom signature flow, not SEP-10, and is not connected to the current wallet interface. Private keys remain in Freighter during frontend transaction signing. All current blockchain operations use Testnet, whose assets have no monetary value.

## Project documentation

- [Frontend setup and implementation](Front-End/IMPLEMENTATION.md)
- [Frontend overview](Front-End/readme.md)
- [Backend setup and wallet API](Back-End/readme.md)
- [Security report](SECURITY_REPORT.md)
