// --- React components/methods
import React, { useEffect, useState } from "react";

// --- Components
import { Input } from "@chakra-ui/react";
import ModalTemplate from "./ModalTemplate";
import { Icon } from "@chakra-ui/icons";
import { HiKey, HiOutlineKey } from "react-icons/hi";
import APIKeyCard from "./APIKeyCard";

// --- Utils
import {
  ApiKeys,
  createApiKey,
  getApiKeys,
  deleteApiKey,
} from "../utils/account-requests";
import NoValues from "./NoValues";

export const ApiKeyList = () => {
  const [apiKeys, setApiKeys] = useState<ApiKeys[]>([]);
  const [error, setError] = useState<undefined | string>();
  const [modalOpen, setModalOpen] = useState(false);
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
  const [newApiKey, setNewApiKey] = useState();
  const [keyName, setKeyName] = useState("");

  useEffect(() => {
    let keysFetched = false;
    const fetchApiKeys = async () => {
      if (keysFetched === false) {
        try {
          const apiKeys = await getApiKeys();
          keysFetched = true;
          setApiKeys(apiKeys);
        } catch (error) {
          console.log({ error });
          setError("There was an error fetching your API keys.");
        }
      }
    };
    fetchApiKeys();
  }, []);

  const handleCreateApiKey = async () => {
    try {
      const apiKey = await createApiKey(keyName);
      setNewApiKey(apiKey.api_key);
      setKeyName("");
      setApiKeys(await getApiKeys());
      setModalOpen(false);
      setApiKeyModalOpen(true);
    } catch (error) {
      setError("There was an error creating your API key.");
    }
  };

  const handleDeleteApiKey = async (apiKeyId: ApiKeys["id"]) => {
    try {
      await deleteApiKey(apiKeyId);
      setApiKeys(await getApiKeys());
    } catch (error) {
      console.error(error);
    }
  };

  const apiKeyList = apiKeys.map((apiKey: ApiKeys, i: number) => {
    return (
      <APIKeyCard
        key={i}
        apiKey={apiKey}
        apiKeyId={apiKey.id}
        handleDeleteApiKey={handleDeleteApiKey}
      />
    );
  });

  if (error) {
    return <div>{error}</div>;
  }

  return (
    <div>
      {apiKeys.length === 0 ? (
        <div>
          <p className="font-librefranklin text-purple-softpurple mb-5">The API’s are composed of communities, scoring mechanisms, and verifiable credentials.</p>
          <NoValues
            title="Create a key"
            description="Request service from communities and interact between applications. The key limit is five."
            addRequest={() => setModalOpen(true)}
            icon={
              <Icon
                as={HiOutlineKey}
                viewBox="-2 -2 18 18"
                boxSize="1.9em"
                color="#6F3FF5"
              />
            }
            buttonText=" API Key"
          />
        </div>
      ) : (
          <div className="grid grid-cols-4 gap-6 h-[40rem] md:h-[45rem]">
            <div className="col-span-3">
              <p className="font-librefranklin text-purple-softpurple pl-1 mb-2">The API’s are composed of communities, scoring mechanisms, and verifiable credentials.</p>
              {apiKeyList}
              {modalOpen}
              {error && <div>{error}</div>}
              <p className="font-librefranklin text-purple-softpurple mt-3 pl-1">The key limit is five.</p>
            </div>
            <div className="grid grid-rows col-span-1">
              <div className="flex flex-col">
                <p className="font-librefranklin text-blue-darkblue mb-2 text-lg">Generate API Keys</p>
                <p className="font-librefranklin text-purple-softpurple mb-4">Request service from communities and interact between applications.</p>
                <button
                  data-testid="open-api-key-modal"
                  className="rounded-sm bg-purple-gitcoinviolet py-2 px-4 text-white"
                  onClick={() => setModalOpen(true)}
                  >
                  <span className="mr-2 text-lg">+</span>Create a key
                </button>
              </div>
            </div>
          </div>
        )}
      <ModalTemplate
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create a key"
        body="Request service from communities and interact between applications. The key limit is five."
        icon={<Icon
          as={HiOutlineKey}
          viewBox="-1 -1 17 17"
          boxSize="2.2em"
          color="#6F3FF5"
        />}
      >
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs mb-2">
            Key name
          </label>
          <Input
            data-testid="key-name-input"
            value={keyName}
            onChange={(name) => setKeyName(name.target.value)}
            placeholder="Key name"
            className="font-librefranklin"
          />
          <div className="flex flex-col w-full justify-end">
            <p className="font-librefranklin text-sm text-purple-softpurple italic mt-7 border-b border-purple-softpurple pb-1">i.e. ‘Gitcoin’, or ‘Snapshot’, or ‘Bankless Academy’, or ‘ENS’, etc.</p>
            <button
              disabled={!keyName}
              data-testid="create-button"
              className="mt-6 mb-2 rounded-sm bg-purple-gitcoinviolet py-2 px-4 text-white disabled:opacity-25"
              onClick={handleCreateApiKey}
            >
              Create
            </button>
          </div>
        </div>
      </ModalTemplate>
      <ModalTemplate
        isOpen={apiKeyModalOpen}
        onClose={() => setApiKeyModalOpen(false)}
        title="Copy your API Key"
        body="Please copy your API key now. You won’t be able to see it again!"
        icon={<Icon
          as={HiOutlineKey}
          viewBox="-1 -1 17 17"
          boxSize="2.2em"
          color="#6F3FF5"
        />}
      >
        <div className="flex flex-col">
          <label className="text-gray-softgray font-librefranklin text-xs">
            API Key
          </label>
          <Input
            className="mb-6 font-librefranklin"
            data-testid="key-name-input"
            value={newApiKey}
            readOnly={true}
          />
        </div>
      </ModalTemplate>
    </div>
  );
};
