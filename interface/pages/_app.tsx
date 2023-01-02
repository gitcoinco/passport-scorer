// --- React components/methods
import React, { useEffect, useState } from "react";

// --- Styling & UI
import "../styles/globals.css";
import "@rainbow-me/rainbowkit/styles.css";
import { ChakraProvider } from "@chakra-ui/react";

// --- Rainbowkit
import {
  connectorsForWallets,
  getDefaultWallets,
  RainbowKitProvider,
  lightTheme,
  RainbowKitAuthenticationProvider,
  AuthenticationStatus,
} from "@rainbow-me/rainbowkit";
import { createAuthenticationAdapter } from "@rainbow-me/rainbowkit";

// --- Next components
import type { AppProps } from "next/app";
import Head from "next/head";
import { useRouter } from "next/router";

// --- Wagmi
import {
  chain,
  configureChains,
  createClient,
  WagmiConfig,
  useConnect,
} from "wagmi";
import { metaMaskWallet } from "@rainbow-me/rainbowkit/wallets";
import { alchemyProvider } from "wagmi/providers/alchemy";
import { publicProvider } from "wagmi/providers/public";

// --- Authentication
import { SiweMessage } from "siwe";

/**
 * @TODO --> prevent wallet list modal from popping up on wallet disconnect
 */
const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;

const { chains, provider, webSocketProvider } = configureChains(
  [chain.mainnet],
  [
    alchemyProvider({
      apiKey: process.env.NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY || "",
    }),
    publicProvider(),
  ]
);

const { wallets } = getDefaultWallets({
  appName: "Passport Scorer as a Service",
  chains,
});

const passportScorerApp = {
  appName: "Passport Scorer as a Service",
};

const connectors = connectorsForWallets([
  ...wallets,
  {
    groupName: "Wallets",
    wallets: [metaMaskWallet({ chains })],
  },
]);

const wagmiClient = createClient({
  autoConnect: true,
  connectors,
  provider,
  webSocketProvider,
});

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const [authenticationStatus, setAuthenticationStatus] =
    useState<AuthenticationStatus>("unauthenticated");

  // Authenticate the user -- interacts with the backend to GET the nonce, create & send back the SIWE message,
  // and receive a response

  const authenticationAdapter = createAuthenticationAdapter({
    getNonce: async () => {
      const response = await fetch(`${SCORER_BACKEND}account/nonce`);
      return (await response.json()).nonce;
    },

    createMessage: ({ nonce, address, chainId }) => {
      return new SiweMessage({
        domain: window.location.host,
        address,
        statement: "Sign in with Ethereum to the app.",
        uri: window.location.origin,
        version: "1",
        chainId,
        nonce,
      });
    },

    getMessageBody: ({ message }) => {
      return message.prepareMessage();
    },

    verify: async ({ message, signature }) => {
      const verifyRes = await fetch(`${SCORER_BACKEND}account/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, signature }),
      });

      if (verifyRes.ok) {
        const data = await verifyRes.json();

        // store JWT access token in LocalStorage
        localStorage.setItem("access-token", data.access);

        setAuthenticationStatus("authenticated");

        router.push("/dashboard/community");
      }

      return Boolean(verifyRes.ok);
    },

    signOut: async () => {
      router.push("/");
    },
  });

  return (
    <>
      <Head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <title>Passport Scorer</title>
      </Head>

      <WagmiConfig client={wagmiClient}>
        <RainbowKitAuthenticationProvider
          adapter={authenticationAdapter}
          status={authenticationStatus}
        >
          <RainbowKitProvider
            appInfo={passportScorerApp}
            chains={chains}
            modalSize="compact"
            theme={lightTheme({
              accentColor: "#6F3FF5",
              accentColorForeground: "white",
              borderRadius: "none",
              overlayBlur: "small",
            })}
          >
            <ChakraProvider>
              <Component
                {...pageProps}
                setAuthenticationStatus={setAuthenticationStatus}
                authenticationStatus={authenticationStatus}
              />
            </ChakraProvider>
          </RainbowKitProvider>{" "}
        </RainbowKitAuthenticationProvider>
      </WagmiConfig>
    </>
  );
}
