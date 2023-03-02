// --- React components/methods
import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/router";

// --- Components
import {
  CheckCircleIcon,
  CloseIcon,
  RepeatIcon,
  AddIcon,
} from "@chakra-ui/icons";
import CommunityCard from "./CommunityCard";
import NoValues from "./NoValues";

// --- Utils
import {
  getCommunities,
  updateCommunity,
  deleteCommunity,
  Community,
} from "../utils/account-requests";

import UseCaseModal from "./UseCaseModal";
import { useToast } from "@chakra-ui/react";

const CommunityList = () => {
  const router = useRouter();
  const toast = useToast();
  const [selectUseCaseModalOpen, setSelectUseCaseModalOpen] = useState(false);
  const [updateCommunityModalOpen, setUpdateCommunityModalOpen] =
    useState(false);
  const [updatedScorerDescription, setUpdatedScorerDescription] = useState("");
  const [updatedScorerName, setUpdatedScorerName] = useState("");
  const [updatedCommunityId, setUpdatedCommunityId] =
    useState<Community["id"]>();
  const [error, setError] = useState<undefined | string>();
  const [communities, setCommunities] = useState<Community[]>([]);

  const fetchCommunities = useCallback(async () => {
    try {
      setCommunities(await getCommunities());
    } catch (error) {
      console.log({ error });
      setError("There was an error fetching your Communities.");
    }
  }, []);

  useEffect(() => {
    const scorerCreated = Boolean(localStorage.getItem("scorerCreated"));

    if (scorerCreated) {
      toast({
        title: "Success!",
        status: "success",
        duration: 3000,
        isClosable: true,
        variant: "solid",
        position: "bottom",
        render: () => (
          <div
            style={{
              backgroundColor: "#0E0333",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              padding: "16px",
            }}
          >
            <CheckCircleIcon color="#02E2AC" boxSize={6} mr={4} />
            <span style={{ color: "white", fontSize: "16px" }}>
              Your Scorer has been created.
            </span>
            <CloseIcon
              color="white"
              boxSize={3}
              ml="8"
              cursor="pointer"
              onClick={() => toast.closeAll()}
            />
          </div>
        ),
      });
      localStorage.removeItem("scoreCreated");
    }

    fetchCommunities();
  }, []);

  const handleDeleteCommunity = async (communityId: Community["id"]) => {
    try {
      await deleteCommunity(communityId);
      await fetchCommunities();
    } catch (error) {
      console.error(error);
    }
  };

  const communityItems = communities.map((community: Community, i: number) => {
    return (
      <CommunityCard
        key={i}
        community={community}
        communityId={community.id}
        setUpdateCommunityModalOpen={setUpdateCommunityModalOpen}
        handleDeleteCommunity={handleDeleteCommunity}
        setUpdatedCommunityId={setUpdatedCommunityId}
        setUpdatedScorerName={setUpdatedScorerName}
        setUpdatedScorerDescription={setUpdatedScorerDescription}
      />
    );
  });

  const communityList = (
    <div className="overflow-hidden bg-white shadow sm:rounded-md">
      <ul role="list" className="divide-y divide-gray-200">
        {communityItems}
      </ul>
    </div>
  );
  return (
    <>
      {communities.length === 0 ? (
        <NoValues
          title="My Communities"
          description="Manage how your dapps interact with the Gitcoin Passport by creating a
        key that will connect to any community."
          addRequest={() => {
            setSelectUseCaseModalOpen(true);
          }}
          icon={
            <RepeatIcon viewBox="0 0 25 25" boxSize="1.9em" color="#757087" />
          }
        />
      ) : (
        <div className="mx-5 mt-4">
          {communityList}

          <div className="mt-5 flex flex-wrap">
            <button
              className="rounded-md bg-purple-gitcoinpurple px-5 py-2 py-3 text-white"
              onClick={() => {
                setSelectUseCaseModalOpen(true);
              }}
              disabled={false}
            >
              <AddIcon className="mr-1" /> Scorer
            </button>
            <p className="ml-5 py-3 text-gray-500">The scorer limit is 5</p>
          </div>
          {error && <div>{error}</div>}
        </div>
      )}
      <UseCaseModal
        isOpen={selectUseCaseModalOpen}
        onClose={() => setSelectUseCaseModalOpen(false)}
      />
    </>
  );
};

export default CommunityList;
