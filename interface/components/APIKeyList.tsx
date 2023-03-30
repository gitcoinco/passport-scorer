// --- React components/methods
import React, { useContext, useEffect, useState, useRef } from "react";

// --- Utils
import {
  ApiKeys,
  getApiKeys,
  deleteApiKey,
  createApiKey,
  updateApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";
import { UserContext } from "../context/userContext";
import {
  ApiKeyCreateModal,
  ApiKeyUpdateModal,
  ApiKeyDeleteModal,
} from "./ApiKeyModal";
import {
  CheckIcon,
  ClipboardDocumentIcon,
  EllipsisVerticalIcon,
  PlusIcon,
} from "@heroicons/react/24/solid";
import {
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  useToast,
} from "@chakra-ui/react";
import { successToast } from "./Toasts";
import { KeyIcon } from "@heroicons/react/24/outline";

import { useClickOutsideToast } from './useClickOutsideToast';

export type ApiKeyDisplay = ApiKeys & {
  api_key?: string;
  copied?: boolean;
};

const APIKeyList = () => {
  const [error, setError] = useState<undefined | string>();
  const [apiKeys, setApiKeys] = useState<ApiKeyDisplay[]>([]);
  const [createApiKeyModal, setCreateApiKeyModal] = useState(false);
  const [apiKeyToDelete, setApiKeyToDelete] = useState<string | undefined>();
  const [apiKeyToUpdate, setApiKeyToUpdate] = useState<string | undefined>();
  const { logout, setUserWarning } = useContext(UserContext);
  const toast = useToast();
  const { openToast } = useClickOutsideToast();

  useEffect(() => {
    let keysFetched = false;
    const fetchApiKeys = async () => {
      if (keysFetched === false) {
        try {
          const apiKeys = await getApiKeys();
          keysFetched = true;
          setApiKeys(apiKeys);
        } catch (error: any) {
          setError("There was an error fetching your API keys.");
          if (error.response.status === 401) {
            logout();
          }
        }
      }
    };
    fetchApiKeys();
  }, []);

  const handleCreateApiKey = async (key: ApiKeyDisplay) => {
    try {
      setCreateApiKeyModal(false);
      openToast(successToast("API Key created successfully!", toast));
      setApiKeys([...apiKeys, key]);
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error creating your API key. Please try again.";
      setError(msg);
    }
  };

  const handleUpdateApiKey = async (
    id: ApiKeys["id"],
    name: ApiKeys["name"]
  ) => {
    try {
      await updateApiKey(id, name);
      setApiKeyToUpdate(undefined);
      openToast(successToast("API Key updated successfully!", toast));

      const apiKeyIndex = apiKeys.findIndex((apiKey) => apiKey.id === id);
      const newApiKeys = [...apiKeys];
      newApiKeys[apiKeyIndex].name = name;

      setApiKeys(newApiKeys);
    } catch (error: any) {
      const msg =
        error?.response?.data?.detail ||
        "There was an error updating your API key. Please try again.";
      setError(msg);
    }
  };

  const handleDeleteApiKey = async (id: ApiKeys["id"]) => {
    try {
      await deleteApiKey(id);
      setApiKeys(await getApiKeys());
    } catch (error: any) {
      if (error.response.status === 401) {
        logout();
      }
    }
  };

  if (error) {
    return <div>{error}</div>;
  }

  const userInstructions = (
    <span className="lg:pt-3 pb-6">
      Use these API keys to programmatically access a Scorer.
    </span>
  );

  return (
    <>
      {apiKeys.length === 0 ? (
        <div className="lg:h-full">
          {userInstructions}
          <NoValues
            title="Generate API Keys"
            description="Interact with the Scorer(s) created via your API key. The key limit is five."
            addActionText="API Key"
            addRequest={() => setCreateApiKeyModal(true)}
            icon={<KeyIcon />}
          />
        </div>
      ) : (
        <>
          <div className="flex w-full flex-col">
            {userInstructions}
            {apiKeys.map((key, i) => (
              <div
                key={`${key.id}-${i}`}
                className={`flex ${key.api_key && "flex-col"
                  } w-full items-center justify-between border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50`}
              >
                <div className="flex w-full items-center justify-between">
                  <div className="justify-self-center text-purple-darkpurple md:justify-self-start">
                    <p>{key.name}</p>
                  </div>

                  <div className="flex">
                    {key.api_key && (
                      <div className="flex items-center pr-5 pl-1">
                        {key.copied ? (
                          <p className="flex text-xs text-purple-gitcoinpurple">
                            Copied! <CheckIcon className="ml-3 w-3.5" />
                          </p>
                        ) : (
                          <>
                            <p className="hidden pr-3 text-xs text-purple-darkpurple md:inline-block">
                              {key.api_key}
                            </p>
                            <button
                              className="mb-1"
                              data-testid="copy-api-key"
                              onClick={async () => {
                                await navigator.clipboard.writeText(
                                  key.api_key!
                                );
                                const updatedKeys = apiKeys.map((k) =>
                                  k.api_key === key.api_key
                                    ? { ...k, copied: true }
                                    : k
                                );
                                setApiKeys(updatedKeys);
                                setUserWarning();
                              }}
                            >
                              <ClipboardDocumentIcon
                                height={14}
                                color={"#0E0333"}
                              />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    <Menu>
                      <MenuButton
                        as={IconButton}
                        icon={
                          <EllipsisVerticalIcon className="h-8 text-purple-darkpurple" />
                        }
                        variant="ghost"
                        _hover={{ bg: "transparent" }}
                        _expanded={{ bg: "transparent" }}
                        _focus={{ bg: "transparent" }}
                      />
                      <MenuList color={"#0E0333"}>
                        <MenuItem onClick={() => setApiKeyToUpdate(key.id)}>
                          Rename
                        </MenuItem>
                        <MenuItem onClick={() => setApiKeyToDelete(key.id)}>
                          Delete
                        </MenuItem>
                      </MenuList>
                    </Menu>
                  </div>
                </div>
                <div className="block max-w-[100%] overflow-hidden md:hidden">
                  {key.api_key && (
                    <div className="flex items-center pr-5 pl-1">
                      {!key.copied && (
                        <p className="pr-3 text-xs text-purple-darkpurple">
                          {key.api_key}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="my-4 flex items-center md:my-6">
            <button
              data-testid="open-api-key-modal"
              className={
                "flex rounded-md bg-purple-gitcoinpurple px-4 py-2 align-middle text-white" +
                (apiKeys.length >= 5
                  ? " cursor-not-allowed disabled:bg-gray-lightgray disabled:text-purple-darkpurple"
                  : "")
              }
              onClick={() => setCreateApiKeyModal(true)}
              disabled={apiKeys.length >= 5}
            >
              <PlusIcon className="mr-2 inline w-6 self-center align-middle" />
              API Key
            </button>
            <p className="ml-6 text-xs text-purple-softpurple">
              The key limit is five.
            </p>
          </div>
          {createApiKeyModal}
          {error && <div>{error}</div>}
        </>
      )}
      <ApiKeyCreateModal
        isOpen={createApiKeyModal}
        onClose={() => setCreateApiKeyModal(false)}
        onCreateApiKey={handleCreateApiKey}
      />
      <ApiKeyUpdateModal
        isOpen={apiKeyToUpdate !== undefined}
        onClose={() => setApiKeyToUpdate(undefined)}
        apiKeyId={apiKeyToUpdate ?? ""}
        onUpdateApiKey={handleUpdateApiKey}
      />
      <ApiKeyDeleteModal
        isOpen={apiKeyToDelete !== undefined}
        onClose={() => setApiKeyToDelete(undefined)}
        apiKeyId={apiKeyToDelete ?? ""}
        onDeleteApiKey={handleDeleteApiKey}
      />
    </>
  );
};

export default APIKeyList;
