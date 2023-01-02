// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import MenuTemplate from "./MenuTemplate";

// --- Next
import { useRouter } from "next/router";

type CommunityCardProps = {
  setUpdatedCommunityName: Function;
  setUpdatedCommunityDescription: Function;
  setUpdatedCommunityId: Function;
  community: Community;
  communityId: Community["id"];
  handleDeleteCommunity: Function;
  setUpdateCommunityModalOpen: Function;
};

const CommunityCard = ({
  community,
  handleDeleteCommunity,
  communityId,
  setUpdateCommunityModalOpen,
  setUpdatedCommunityName,
  setUpdatedCommunityDescription,
  setUpdatedCommunityId,
}: CommunityCardProps): JSX.Element => {
  const router = useRouter();

  const menuItems = [
    {
      label: "Edit",
      onClick: () => {
        setUpdatedCommunityName(community.name);
        setUpdatedCommunityDescription(community.description);
        setUpdatedCommunityId(community.id);
        setUpdateCommunityModalOpen(true);
      }
    },
    {
      label: "Delete",
      onClick: async () => await handleDeleteCommunity(communityId)
    },
  ];

  return (
    <div className="grid w-full auto-cols-auto grid-cols-2 items-center justify-between border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50">
      {/* first column */}
      <div className="grid-rows grid">
        <p className="mb-2 cursor-pointer font-librefranklin font-semibold text-blue-darkblue">
          <a
            onClick={() => router.push({
              pathname: `/dashboard/community/${community.id}`,
              query: {
                id: community.id,
                communityName: community.name,
                communityDescription: community.description,
              }
            })}
          >
            {community.name}
          </a>
        </p>
        <p className="font-librefranklin text-purple-softpurple">
          {community.description}
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

export default CommunityCard;
