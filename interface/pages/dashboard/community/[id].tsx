import { useEffect, useState } from "react";

// Next
import { useRouter } from "next/router";

// Components
import { Layout } from "../../../components/Layout";
import { Radio, RadioGroup } from "@chakra-ui/react";
import { InfoIcon } from "@chakra-ui/icons";
import PopoverTemplate from "../../../components/PopoverTemplate";

// Requests
import {
  getCommunityScorers,
  Scorer,
  updateCommunityScorers,
} from "../../../utils/account-requests";

const defaultScorer = {
  name: "Gitcoin Scoring",
  description:
    "Stamps and data are binarily verified, aggregated, and scored relative to all other attestations.",
  id: "gitcoin",
};

const defaultScorers = [defaultScorer];

const Community = () => {
  const [activeScorer, setActiveScorer] = useState("gitcoin");

  const router = useRouter();
  const [scorers, setScorers] = useState<Scorer[]>([]);

  const { id } = router.query;

  const updateScorer = async (communityId: string, scorerId: string) => {
    await updateCommunityScorers(communityId, scorerId);
    const communityScorers = await getCommunityScorers(id as string);
    setActiveScorer(communityScorers.currentScorer || "");
  };

  useEffect(() => {
    const getScorers = async () => {
      if (!id) {
        setScorers([]);
        return;
      }
      const communityScorers = await getCommunityScorers(id as string);

      setScorers(communityScorers.scorers);
      setActiveScorer(communityScorers.currentScorer || "");
    };
    getScorers();
  }, [id]);

  return (
    <>
      <Layout>
        <p className="font-librefranklin text-purple-softpurple mb-4">Scoring mechanisms establish identity rules within communities that fit the application's needs.</p>
        <div className="grid grid-cols-5 grid-row gap-4">
          {/* Deduplication */}
          <aside className="col-span-1">
            <p className="mb-2 font-librefranklin text-blue-dark">Deduplication <span><InfoIcon /></span></p>
            <div className="bg-white border border-gray-lightgray rounded-md p-3">
              <p className="font-librefranklin text-purple-softpurple mb-4 text-sm">When duplicates are found, should Passport score through the first or last one created?</p>
            </div>
          </aside>
          <section className="col-span-4">
            {/* Weighted Scorer */}
            <p className="mb-2 font-librefranklin text-blue-dark">Default <span><InfoIcon /></span></p>
            {scorers.map((scorer) => (
              <div
                key={scorer.id}
                className="flex w-full justify-start border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
              >
                {/* first column */}
                <RadioGroup
                  className="mt-4"
                  onChange={setActiveScorer}
                  value={activeScorer}
                >
                  <Radio
                    data-testid={`radio-${scorer.id}`}
                    colorScheme={"purple"}
                    value={scorer.id}
                    className="mr-4"
                    onChange={() => updateScorer(id as string, scorer.id)}
                  >
                    <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">
                      {scorer.label}
                    </p>
                    {/* <p className="font-librefranklin text-purple-softpurple">
                      {scorer.description}
                    </p> */}
                  </Radio>
                </RadioGroup>
              </div>
            ))}

            {/* Customized Scoring */}
          </section>
          <section className="col-start-2 col-span-4">
            <div className="mt-6">
              <p className="font-librefranklin text-blue-dark mb-2">Customize <span><InfoIcon /></span></p>
              <div
                className="flex flex-col w-full justify-start border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
              >
                <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">Select stamps, data, and  weights for attestations.</p>
                <p className="font-librefranklin text-purple-softpurple">Select the verified credentials and/or data points you want Gitcoin Passport to score.</p>
              </div>
            </div>
          </section>
        </div>

      </Layout>
      <PopoverTemplate

      />
    </>
  );
};

export default Community;
