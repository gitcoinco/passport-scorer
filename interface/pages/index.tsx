// --- React Methods
import React from "react";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";
import { ConnectButton } from "@rainbow-me/rainbowkit";

export default function Home() {

  return (
    <>
      <Header />
      <div className="container mx-auto px-5 py-2 h-full">
        <div className="mt-0 w-full pb-6 text-white sm:mt-40 sm:w-1/2 md:mt-40 md:w-1/2 md:pt-6">
          <div className="font-miriam-libre leading-relaxed">
            <img src="/assets/gitcoinWordLogo.svg" alt="Passport Logo" className="py-4 px-1" />
            <p className="text-5xl sm:text-7xl md:text-7xl text-blue-darkblue">Passport</p>
          </div>
          <div className="font-libre-franklin text-lg text-blue-darkblue sm:text-xl mt-8 md:mt-10 md:pr-20 md:text-xl w-5/6 line">
            <p>Gitcoin Passport is an identity protocol that proves your trustworthiness without needing to collect personally identifiable information.</p>
          </div>
          <div className="mt-4 w-full sm:mt-10 sm:w-1/2 md:mt-10 md:block md:w-1/2">
            <ConnectButton label="Connect Wallet" />
          </div>
          <div>
            <p className="font-libre-franklin text-blue-darkblue text-md mt-8 md:mt-6 md:pr-20">Are you a builder or a DAO? <a className="underline" href="#" target="_blank">Learn how to build on Passport.</a></p>
          </div>
        </div>
      </div>
      <div className="mt-12">
        <Footer />
      </div>
    </>
  );
};
