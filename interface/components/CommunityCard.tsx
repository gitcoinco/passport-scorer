// --- React components/methods
import React, { useState, useEffect } from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components

import {
  NoSymbolIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";

// --- Next
import { useRouter } from "next/router";

import {
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Icon,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  Input,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useToast,
  UseToastOptions,
} from "@chakra-ui/react";
import { CloseIcon } from "@chakra-ui/icons";
import { UseCaseInterface, useCases } from "./UseCaseModal";
import { SpinnerIcon } from "./CustomIcons";
import { useClickOutsideToast } from "./useClickOutsideToast";
import { warningToast } from "./Toasts";

interface UseCaseMap {
  [k: string]: UseCaseInterface;
}

const useCasesByName = useCases.reduce(
  (acc: UseCaseMap, useCase: UseCaseInterface) => {
    acc[useCase.title] = useCase;
    return acc;
  },
  {} as UseCaseMap
);

type CommunityCardProps = {
  community: Community;
  onCommunityDeleted: () => void;

  handleUpdateCommunity: (
    communityId: number,
    name: string,
    description: string
  ) => void;
  handleDeleteCommunity: (communityId: number) => void;
};

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveChanges: (name: string, description: string) => void;
  name: string;
  description: string;
}

const RenameModal = ({
  isOpen,
  onClose,
  onSaveChanges,
  name,
  description,
}: RenameModalProps): JSX.Element => {
  const [scorerName, setScorerName] = useState("");
  const [scorerDescription, setScorerDescription] = useState("");
  const [inProgress, setInProgress] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setScorerName(name);
      setScorerDescription(description);
    }
  }, [isOpen]);

  const closeModal = () => {
    onClose();
  };

  const saveChanges = async () => {
    setInProgress(true);
    try {
      await onSaveChanges(scorerName, scorerDescription);
    } catch (e) { }
    setInProgress(false);
  };

  return (
    <Modal
      isOpen={isOpen}
      isCentered={true}
      size={{ base: "full", md: "xl", lg: "xl", xl: "xl" }}
      onClose={closeModal}
    >
      <ModalOverlay />
      <ModalContent>
        <ModalHeader className="flex justify-center">
          <span className="text-base font-normal">Rename Scorer</span>
        </ModalHeader>
        <ModalCloseButton onClick={closeModal} />
        <ModalBody className="flex h-screen w-full flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            Name
          </label>
          <Input
            data-testid="use-case-name-input"
            className="mt-2 mb-4 text-blue-darkblue"
            value={scorerName}
            onChange={(name) => setScorerName(name.target.value)}
            placeholder="App / Use Case Name"
          />
          <label className="text-gray-softgray font-librefranklin text-xs">
            Description
          </label>{" "}
          <Input
            className="mt-2 text-blue-darkblue"
            data-testid="use-case-description-input"
            value={scorerDescription}
            onChange={(description) =>
              setScorerDescription(description.target.value)
            }
            placeholder="Enter Use Case Description"
          />
        </ModalBody>
        <ModalFooter>
          <button
            className="mb-2 flex w-full justify-center rounded-md bg-purple-gitcoinpurple py-3 text-white md:mt-4"
            disabled={!scorerName || !scorerDescription || inProgress}
            onClick={saveChanges}
          >
            <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
            Save Changes
          </button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

interface DeleteConfirmationModalProps {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  community: Community;
}

const DeleteConfirmationModal = ({
  isOpen,
  onCancel,
  onConfirm,
}: DeleteConfirmationModalProps): JSX.Element => {
  const [inProgress, setInProgress] = useState(false);

  const handleDeleteConfirm = async () => {
    setInProgress(true);
    try {
      await onConfirm();
    } catch (e) { }
    setInProgress(false);
  };
  return (
    <Modal
      isOpen={isOpen}
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
                This will permanantly delete your scorer.
                <br />
                Are you sure you want to continue?
              </p>
            </div>
            <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2">
              <button
                className="order-last w-full rounded border border-gray-lightgray py-2 px-6 text-base md:order-first"
                onClick={onCancel}
              >
                Cancel
              </button>
              <button
                className="flex w-full justify-center rounded bg-purple-gitcoinpurple py-2 px-6 text-base text-white"
                onClick={handleDeleteConfirm}
                disabled={inProgress}
              >
                <SpinnerIcon inProgress={inProgress}></SpinnerIcon>
                Confirm Deletion
              </button>
            </div>
          </div>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

const getErrorToast = (toast: ReturnType<typeof useToast>): UseToastOptions => {
  return {
    title: "Warning!",
    status: "warning",
    duration: 3000,
    isClosable: true,
    variant: "solid",
    position: "bottom",
    render: () => (
      <div
        style={{
          backgroundColor: "#FDDEE4",
          borderRadius: "4px",
          display: "flex",
          alignItems: "center",
          padding: "16px",
        }}
      >
        <ExclamationCircleIcon className="mr-3 w-6 text-[#D44D6E]" />
        <span style={{ color: "#0E0333", fontSize: "16px" }}>
          Something went wrong. Please try again.
        </span>
        <CloseIcon
          color="#0E0333"
          boxSize={3}
          ml="8"
          cursor="pointer"
          onClick={() => toast.closeAll()}
        />
      </div>
    ),
  };
};

const CommunityCard = ({
  community,
  handleUpdateCommunity,
  handleDeleteCommunity,
}: CommunityCardProps): JSX.Element => {
  const toast = useToast();
  const { openToast } = useClickOutsideToast();
  let useCase = useCasesByName[community.use_case];
  let [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  let [isDeleteConfirmationModalOpen, setIsDeleteConfirmationModalOpen] =
    useState(false);

  const handleRename = () => {
    setIsRenameModalOpen(true);
  };

  const handleCloseRenameModal = () => {
    setIsRenameModalOpen(false);
  };

  const handleDelete = () => {
    setIsDeleteConfirmationModalOpen(true);
  };
  const handleCancelDelete = () => {
    try {
      setIsDeleteConfirmationModalOpen(false);
    } catch (e) { }
  };

  const saveChanges = async (name: string, description: string) => {
    try {
      await handleUpdateCommunity(community.id, name, description);
      setIsRenameModalOpen(false);
    } catch (e) {
      openToast(warningToast("Something went wrong. Please try again.", toast));
    }
  };

  const deleteCommunity = async () => {
    try {
      await handleDeleteCommunity(community.id);
      setIsDeleteConfirmationModalOpen(false);
    } catch (e) {
      openToast(warningToast("Something went wrong. Please try again.", toast));
    }
  };

  const useCaseIcon = useCase ? (
    <Icon boxSize={19.5}>{useCase.icon("#6F3FF5")}</Icon>
  ) : null;
  return (
    <div className="flex-col px-4 py-4 md:px-6">
      <RenameModal
        isOpen={isRenameModalOpen}
        onClose={handleCloseRenameModal}
        onSaveChanges={saveChanges}
        name={community.name}
        description={community.description}
      ></RenameModal>
      <DeleteConfirmationModal
        isOpen={isDeleteConfirmationModalOpen}
        onCancel={handleCancelDelete}
        onConfirm={deleteCommunity}
        community={community}
      ></DeleteConfirmationModal>
      <div
        data-testid={`scorer-item-${community.id}`}
        className="relative min-w-0 md:static md:flex"
      >
        <div className="flex-auto md:basis-5/12">
          <p className="text-sm text-purple-gitcoinpurple">
            {useCaseIcon}
            {useCase?.title}
          </p>
          <p className="truncate text-base font-medium text-purple-darkpurple">
            {community.name}
          </p>
          <p className="mt-2 flex items-center text-sm text-purple-softpurple">
            <span className="truncate">{community.description}</span>
          </p>
        </div>
        <div className="mt-4 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            Created:
          </p>
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            {community.created_at
              ? new Date(community.created_at).toDateString()
              : ""}
          </p>
        </div>
        <div className="mt-1 flex md:mt-5 md:block md:basis-3/12">
          <p className="text-right text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            Scorer ID:
          </p>
          <p className="text-sm text-purple-softpurple md:flex md:flex-row-reverse">
            {community.id}
          </p>
        </div>
        <div className="absolute top-0 right-0 md:static md:flex md:basis-1/12 md:flex-row-reverse">
          <Menu>
            <MenuButton data-testid="card-menu-button">
              <div className="m-auto flex justify-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="h-6 w-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z"
                  />
                </svg>
              </div>
            </MenuButton>{" "}
            <MenuList>
              <MenuItem
                data-testid={`menu-rename-${community.id}`}
                onClick={handleRename}
              >
                Rename
              </MenuItem>
              <MenuItem
                data-testid={`menu-delete-${community.id}`}
                onClick={handleDelete}
              >
                Delete
              </MenuItem>
            </MenuList>
          </Menu>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
