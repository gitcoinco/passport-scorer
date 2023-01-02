// --- React components/methods
import React from "react";

// --- Types
import { ApiKeys } from "../utils/account-requests";

// Components
import MenuTemplate from "./MenuTemplate";


type APIKeyCardProps = {
  key: number;
  apiKey: ApiKeys;
  apiKeyId: ApiKeys["id"];
  handleDeleteApiKey: Function;
};

const APIKeyCard = ({
  key,
  apiKey,
  handleDeleteApiKey,
  apiKeyId,
}: APIKeyCardProps): JSX.Element => {

  const menuItems = [
    {
      label: "Delete",
      onClick: async () => await handleDeleteApiKey(apiKeyId)
    }
  ];

  return (
    <div className="grid w-full auto-cols-auto grid-cols-2 items-center justify-between border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50">
      {/* first column */}
      <div className="grid-rows grid">
        <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">
          {apiKey.name}
        </p>
      </div>
      {/* second column */}
      <div className="grid grid-cols-1 justify-self-end">
        <MenuTemplate>
          {menuItems}
        </MenuTemplate>
      </div>
    </div>
  );
};

export default APIKeyCard;
