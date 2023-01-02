// --- React components/methods
import React, { useState } from "react";

// --- Next components
import Router, { NextRouter, useRouter } from "next/router";

// --- Components
import Header from "../components/Header";
import { Icon, QuestionIcon, ArrowBackIcon } from "@chakra-ui/icons";
import { HiKey } from "react-icons/hi";
import { IoIosPeople } from "react-icons/io";
import ModalTemplate from "./ModalTemplate";


type LayoutProps = {
  children: React.ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const [welcomeModalOpen, setWelcomeModalOpen] = useState(false);
  const [encryptedModalOpen, setEncryptedModalOpen] = useState(false);
  const [customModalOpen, setCustomModalOpen] = useState(false);
  const router = useRouter();

  const tabbedClasses = (route: string) => {
    const base = "my-4 flex leading-4 cursor-pointer text-left";
    return router.pathname.includes(route) ? `${base} font-bold text-purple-gitcoinviolet bg-white py-2 pr-9 pl-2 rounded-sm` : `${base} text-blue-darkblue`;
  };

  return (
    <div>
      <Header />
      <div className="grid grid-cols-4 w-11/12 mx-auto">
        <div className="mt-0 py-4 text-black col-span-3">
          {
            router.asPath.includes(`/dashboard/community/${router.query.id}`) ? (
              <>
                <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
                  {router.query.communityName}
                </h1>
                <p className="mt-2 mb-7 font-librefranklin text-purple-softpurple">
                  {router.query.communityDescription}
                </p>
                <div>
                  <a
                    onClick={() => router.push('/dashboard')}
                    className="flex flex-row items-center font-librefranklin text-purple-gitcoinviolet cursor-pointer"
                  >
                    <ArrowBackIcon className="mr-2" />
                    Back
                  </a>
                </div>
              </>
            ) : (
              <>
                <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
                  Scoring Dashboard
                </h1>
                <p className="mt-2 font-librefranklin text-purple-softpurple">
                Create a community and API key to interact with and score eligibility using Gitcoin Passport.
                </p>
              </>
            )
          }
        </div>
        <div className="flex col-span-1 items-center justify-self-end">
          <button
            className="border border-gray-lightgray p-2 rounded"
            onClick={() => setWelcomeModalOpen(true)}
            data-testid="passport-scoring-info-button"
          >
            {welcomeModalOpen}
            <QuestionIcon className="float-right" />
          </button>
        </div>
      </div>
      <div className="flex bg-gray-bluegray py-4 border-t border-gray-300 px-14">
        {
          router.asPath.includes(`/dashboard/community/${router.query.id}`) ? (
            <div></div>
          ) : (
            <div className="my-4 min-h-full w-1/5 flex-col">
              <button
                data-testid="communities-tab"
                onClick={() => router.push("/dashboard/community")}
                className={tabbedClasses("community")}
              >
                <Icon as={IoIosPeople} className="mr-2" />Communities
              </button>
              <button
                data-testid="api-keys-tab"
                onClick={() => router.push("/dashboard/api-keys")}
                className={tabbedClasses("api-keys")}
              >
                <Icon as={HiKey} className="mr-2" /> API Keys
              </button>
            </div>
          )
        }
        <div className="flex min-h-full w-full flex-col p-6 md:h-screen">
          {children}
        </div>
      </div>
      <ModalTemplate
        isOpen={welcomeModalOpen}
        onClose={() => setWelcomeModalOpen(false)}
        title="Welcome to Passport Scoring!"
        body="Now we have the capability to easily score Passports for eligibility in grants programs, apps, projects, and more!"
        imageUrl="../assets/placeholderImage.svg"
        imageAlt="tbd"
      >
        <div className="grid grid-cols-2">
          <button
            onClick={() => setWelcomeModalOpen(false)}
            className="mt-6 mb-2 w-1/4 justify-self-start font-librefranklin text-blue-darkblue"
            data-testid="info-welcome-skip-button"
          >Skip</button>
          <button
            data-testid="info-encrypted-button"
            className="mt-6 mb-2 rounded-sm bg-purple-gitcoinviolet py-2 px-4 text-white disabled:opacity-25 w-2/4 justify-self-end"
            onClick={() => {
              setEncryptedModalOpen(true)
              setWelcomeModalOpen(false)
            }}
          >Next</button>
        </div>
      </ModalTemplate>
      <ModalTemplate
        isOpen={encryptedModalOpen}
        onClose={() => setEncryptedModalOpen(false)}
        title="Encrypted API Key Strings"
        body="Generate up to five API key strings, use them to connect to your communities."
        imageUrl="../assets/placeholderImage.svg"
        imageAlt="tbd"
      >
        <div className="grid grid-cols-2">
          <button
            onClick={() => setEncryptedModalOpen(false)}
            className="mt-6 mb-2 w-1/4 justify-self-start font-librefranklin text-blue-darkblue"
            data-testid="info-encrypted-skip-button"
          >Skip</button>
          <div className="flex justify-end">
            <button
              data-testid="info-custom-button"
              className="mt-6 mb-2 rounded-sm bg-white border border-gray-lightgray py-2 px-4 text-blue-darkblue font-librefranklin justify-self-end w-2/4"
              onClick={() => {
                setWelcomeModalOpen(true)
                setEncryptedModalOpen(false)
              }}
            >Previous</button>
            <button
              data-testid="info-welcome-button"
              className="mt-6 mb-2 rounded-sm bg-purple-gitcoinviolet py-2 px-4 text-white disabled:opacity-25 w-2/4 ml-2 justify-self-end"
              onClick={() => {
                setCustomModalOpen(true)
                setEncryptedModalOpen(false)
              }}
            >Next</button>

          </div>
        </div>
      </ModalTemplate>
      <ModalTemplate
        isOpen={customModalOpen}
        onClose={() => setCustomModalOpen(false)}
        title="Customized Scoring"
        body="Select between Gitcoin generated scoring or deeply customize weight and elligibility criteria per each stamp and data attestation."
        imageUrl="../assets/placeholderImage.svg"
        imageAlt="tbd"
      >
        <div className="flex justify-end">
          <button
            data-testid="info-custom-button"
            className="mt-6 mb-2 rounded-sm bg-white border border-gray-lightgray py-2 px-4 text-blue-darkblue font-librefranklin w-1/4"
            onClick={() => {
              setEncryptedModalOpen(true)
              setCustomModalOpen(false)
            }}
          >Previous</button>
          <button
            data-testid="passport-info-done-button"
            className="mt-6 mb-2 rounded-sm bg-purple-gitcoinviolet py-2 px-4 text-white disabled:opacity-25 w-1/4 ml-2"
            onClick={() => {
              setCustomModalOpen(false)
            }}
          >Done</button>
        </div>
      </ModalTemplate>
    </div>
  )
};
