import { useNavigate } from "react-router-dom";
import {
  Icon,
  Modal,
  ModalBody,
  ModalContent,
  ModalOverlay,
  Select,
  useToast,
} from "@chakra-ui/react";
import {
  ExclamationCircleIcon,
  NoSymbolIcon,
} from "@heroicons/react/24/outline";
import {
  ChartPieIcon,
  ScaleIcon,
  CurrencyDollarIcon,
  AdjustmentsVerticalIcon,
} from "@heroicons/react/24/outline";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import PageWidthGrid from "./PageWidthGrid";
import { PAGE_PADDING } from "./PageLayout";
import HeaderContentFooterGrid from "./HeaderContentFooterGrid";
import Header from "./Header";

import { UseCaseInterface, useCases } from "./UseCaseModal";
import { createCommunity } from "../utils/account-requests";
import { CloseIcon } from "@chakra-ui/icons";
import PopoverInfo from "./PopoverInfo";
import { useClickOutsideToast } from "./useClickOutsideToast";
import { warningToast } from "./Toasts";

type DeduplicationType = "FIFO" | "LIFO";

interface GitcoinScoringMechanismInterface {
  icon: (classes?: string) => JSX.Element;
  title: string;
  apiTitle: string;
  description: string;
  badge?: string;
  disabled?: boolean;
  recommended?: boolean;
}

export const gitcoinScoringMechanisms: Array<GitcoinScoringMechanismInterface> =
  [
    {
      icon: (classes: string = ""): JSX.Element => (
        <ChartPieIcon className={classes} />
      ),
      title: "Unique Humanity",
      apiTitle: "WEIGHTED",
      description:
        "Stamp data is evaluated and scored on a  0-100 scale where 100 includes collection of ALL stamps available. Setting a threshold above 20 will greatly reduce bad actors.",
      badge: "Recommended",
      recommended: true,
    },
    {
      icon: (classes: string = ""): JSX.Element => (
        <ScaleIcon className={classes} />
      ),
      title: "Unique Humanity (Binary)",
      apiTitle: "WEIGHTED_BINARY",
      description:
        "Stamp data is verified in a binary system, the data is aggregated, and scored relative to all other verifications.",
    },
    {
      icon: (classes: string = ""): JSX.Element => (
        <CurrencyDollarIcon className={classes} />
      ),
      title: "Cost of Forgery",
      apiTitle: "COST_OF_FORGERY",
      description:
        "This is the USD  value of a Passport and can be used to determine  rewards/access in app. Setting a threshold equal to the value being delivered will reduce bad actors.",
      badge: "Coming Soon",
      disabled: true,
    },
  ];

const PageFooter = ({
  setCancelModal,
  createScorer,
  gitcoinScoringMechanism,
  cancelModal,
  handleCancellation,
  deduplication,
  isLoading,
}: any) => (
  <footer
    className={
      `mt-6 w-full border-t border-gray-lightgray bg-white py-6 fixed inset-x-0 bottom-0 ` + PAGE_PADDING
    }
  >
    <div className="mx-auto overflow-hidden md:flex md:justify-end">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <button
          className="order-last h-10 w-full rounded border border-gray-lightgray px-6 text-sm md:order-first md:w-[139px]"
          onClick={() => setCancelModal(true)}
        >
          Cancel
        </button>
        <button
          className="h-10 w-full rounded bg-purple-gitcoinpurple text-sm text-white md:w-36"
          onClick={createScorer}
          disabled={!gitcoinScoringMechanism || !deduplication || isLoading}
        >
          Create Scorer
        </button>
      </div>
    </div>
    <Modal
      isOpen={cancelModal}
      isCentered={true}
      size={{ base: "xs", md: "lg", lg: "lg", xl: "lg" }}
      onClose={() => { }}
    >
      <ModalOverlay />
      <ModalContent>
        <ModalBody>
          <div className="py-6 text-purple-darkpurple">
            <div className="flex items-center justify-center">
              <div className="mb-4 flex h-12 w-12 justify-center rounded-full bg-[#FDDEE4]">
                <NoSymbolIcon className="w-7 text-[#D44D6E]" />
              </div>
            </div>
            <div className="text-center">
              <p className="font-bold">Are you sure?</p>
              <p className="mt-2 text-purple-softpurple">
                Your scorer has not been saved, if you exit now your changes
                will not be saved.
              </p>
            </div>
            <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
              <button
                className="order-last w-full rounded border border-gray-lightgray py-2 px-6 text-base md:order-first"
                onClick={handleCancellation}
              >
                Exit Scorer
              </button>
              <button
                className="w-full rounded bg-purple-gitcoinpurple py-2 px-6 text-base text-white"
                onClick={() => setCancelModal(false)}
              >
                Continue Editing
              </button>
            </div>
          </div>
        </ModalBody>
      </ModalContent>
    </Modal>
  </footer>
);

const Subheader = ({ useCase, name, description }: any) => (
  <div className="my-6 flex w-full justify-between">
    <div>
      <p className="text-xs text-purple-softpurple">
        Select a Scoring Mechanism
      </p>
      <p className="mt-2 text-purple-gitcoinpurple">
        <Icon boxSize={19.5}>{useCase?.icon("#6F3FF5")}</Icon> {useCase?.title}
      </p>

      <h1 className="mt-2 font-miriamlibre text-2xl">{name}</h1>
      <p className="mt-2 text-purple-softpurple">{description}</p>
    </div>
    <div>
      <p className="mb-2 text-xs text-purple-softpurple">Scorer ID</p>
      <p>N/A</p>
    </div>
  </div>
);

const NewScorer = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const { openToast } = useClickOutsideToast();
  const [useCase, setUseCase] = useState<UseCaseInterface | undefined>(
    undefined
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [deduplication, setDeduplication] = useState<DeduplicationType>("LIFO");
  const [gitcoinScoringMechanism, setGitcoinScoringMechanism] = useState<
    GitcoinScoringMechanismInterface | undefined
  >(undefined);

  const [isLoading, setIsLoading] = useState(false);
  const [cancelModal, setCancelModal] = useState(false);

  useEffect(() => {
    const scorer =
      JSON.parse(localStorage.getItem("tempScorer") || "null") || {};

    if (Object.keys(scorer).length > 0) {
      const useCase = useCases[scorer.useCase];
      setUseCase(useCase);
      setName(scorer.name);
      setDescription(scorer.description);
    }
  }, []);

  const handleCancellation = useCallback(() => {
    localStorage.removeItem("tempScorer");
    navigate("/dashboard/scorer");
  }, [navigate]);

  const createScorer = useCallback(async () => {
    try {
      setIsLoading(true);
      await createCommunity({
        name,
        description,
        use_case: useCase!.title,
        rule: deduplication,
        scorer: gitcoinScoringMechanism!.apiTitle,
      });
      localStorage.setItem("scorerCreated", "true");
      navigate("/dashboard/scorer");
    } catch (e) {
      openToast(warningToast("Something went wrong. Please try again.", toast));
      // {
      //   title: "Warning!",
      //   status: "warning",
      //   duration: 3000,
      //   isClosable: true,
      //   variant: "solid",
      //   position: "bottom",
      //   render: () => (
      //     <div
      //       style={{
      //         backgroundColor: "#FDDEE4",
      //         borderRadius: "4px",
      //         display: "flex",
      //         alignItems: "center",
      //         padding: "16px",
      //       }}
      //     >
      //       <ExclamationCircleIcon className="mr-3 w-6 text-[#D44D6E]" />
      //       <span style={{ color: "#0E0333", fontSize: "16px" }}>
      //         Something went wrong. Please try again.
      //       </span>
      //       <CloseIcon
      //         color="#0E0333"
      //         boxSize={3}
      //         ml="8"
      //         cursor="pointer"
      //         onClick={() => toast.closeAll()}
      //       />
      //     </div>
      //   ),
      // }
    }
  }, [
    name,
    description,
    useCase,
    deduplication,
    gitcoinScoringMechanism,
    navigate,
    toast,
  ]);

  return (
    <HeaderContentFooterGrid>
      <Header
        subheader={
          <Subheader name={name} description={description} useCase={useCase} />
        }
      />
      <PageWidthGrid className="mt-4 h-fit">
        <p className="col-span-4 text-purple-softpurple md:col-span-6 lg:col-span-8 xl:col-span-12">
          Scoring mechanisms establish identity rules within Scorers. Scorers
          cannot be changed after creating them, but multiple Scorers can be
          created.
        </p>
        <div className="col-span-4 md:col-span-6 lg:col-span-2 xl:col-span-3">
          <span className="mr-1 text-xs">Select Deduplication</span>
          <PopoverInfo>
            Gitcoin scoring uses binary logic to verify stamp/account ownership,
            encrypted for privacy and to decrease deduplication risk.
            <br />
            <a
              href="https://docs.passport.gitcoin.co"
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-jade underline"
            >
              Learn More
            </a>
          </PopoverInfo>
        </div>
        <div className="col-span-4 md:col-span-3 md:row-start-3 lg:col-span-2 lg:row-end-5 xl:col-span-3">
          <div className="rounded border border-gray-lightgray bg-white p-6 text-purple-softpurple">
            <p className="mb-6 text-xs">
              If duplicate Verified Credentials s are found, should Passport
              score through the first or last one created?
            </p>
            <Select
              iconColor="#0E0333"
              className="w-full rounded border border-gray-lightgray px-4"
              onChange={(e: any) => setDeduplication(e.target.value)}
            >
              <option value="LIFO">Last in first out (default)</option>
              <option value="FIFO">First in first out</option>
            </Select>
          </div>
        </div>

        <div className="col-span-4 md:col-span-6 xl:col-span-9">
          <span className="mr-1 text-xs">Scoring Mechanisms</span>
          <PopoverInfo>
            The scoring rules evaluate Passports based on the &quot;Verifiable
            Credentials&quot; (VCs), or &quot;Stamps&quot; they hold.
          </PopoverInfo>
        </div>

        {gitcoinScoringMechanisms.map((mechanism, index) => (
          <div
            key={index}
            data-testid={`scoring-mechanism-${index}`}
            onClick={() => setGitcoinScoringMechanism(mechanism)}
            className={
              "col-span-4 rounded border border-gray-lightgray bg-white p-6 md:col-span-3 " +
              (!mechanism.disabled
                ? "cursor-pointer " +
                (gitcoinScoringMechanism?.title === mechanism.title
                  ? "outline outline-2 outline-purple-gitcoinpurple"
                  : "hover:border-purple-gitcoinpurple")
                : "cursor-not-allowed")
            }
          >
            <div className="flex items-center justify-between">
              <div
                className={
                  "flex h-12 w-12 items-center justify-center rounded-full " +
                  (mechanism.recommended
                    ? "bg-[#F0EBFF]"
                    : "border border-gray-lightgray")
                }
              >
                {mechanism.icon(
                  `w-7 ${mechanism.recommended
                    ? "text-purple-gitcoinpurple"
                    : "text-purple-darkpurple"
                  }`
                )}
              </div>
              {mechanism.badge && (
                <div
                  className={
                    "rounded-xl px-2 py-1 text-xs " +
                    (mechanism.recommended
                      ? "bg-[#F0EBFF] text-purple-gitcoinpurple"
                      : "bg-gray-lightgray text-blue-darkblue")
                  }
                >
                  <span>{mechanism.badge}</span>
                </div>
              )}
            </div>
            <div>
              <p className="mt-6 mb-4 text-sm text-blue-darkblue">
                {mechanism.title}
              </p>
              <p className="text-xs text-purple-softpurple">
                {mechanism.description}
              </p>
            </div>
          </div>
        ))}
        <div className="col-span-4 cursor-not-allowed rounded border border-gray-lightgray bg-white p-6 md:col-span-3">
          <div className="flex items-center justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-gray-lightgray">
              <AdjustmentsVerticalIcon className="w-7 text-purple-darkpurple" />
            </div>
            <div className="rounded-xl bg-gray-lightgray px-2 py-1 text-xs text-blue-darkblue">
              <span>Coming soon</span>
            </div>
          </div>
          <div>
            <p className="mt-6 mb-4 text-sm text-blue-darkblue">Customize</p>
            <p className="text-xs text-purple-softpurple">
              Configure stamp weights for you community and define a score that
              is truly customized to your use case (this is an advanced
              scenario).
            </p>
          </div>
        </div>
      </PageWidthGrid>
      <PageFooter
        setCancelModal={setCancelModal}
        createScorer={createScorer}
        gitcoinScoringMechanism={gitcoinScoringMechanism}
        cancelModal={cancelModal}
        handleCancellation={handleCancellation}
        deduplication={deduplication}
        isLoading={isLoading}
      />
    </HeaderContentFooterGrid>
  );
};

export default NewScorer;
