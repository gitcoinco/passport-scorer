"""Configuration for the gitcoin scorer"""

# Weight values for each stamp based on its perceived significance in assessing the unique humanity of the Passport holder
GITCOIN_PASSPORT_WEIGHTS = {
    "Brightid": "1.52628630764708",
    "CommunityStakingBronze": "2.46650364273423",
    "CommunityStakingGold": "1.74744709515098",
    "CommunityStakingSilver": "2.10880999350127",
    "Discord": "1.55584005440946",
    "Ens": "1.61051768191486",
    "EthGTEOneTxnProvider": "1.57291787116619",
    "ETHGasSpent.5": "1.57425115793055",
    "Facebook": "1.58978370685981",
    "FacebookProfilePicture": "1.58944635871072",
    "FacebookFriends100": "1.58944635871072",
    "FiftyOrMoreGithubFollowers": "1.49715263623493",
    "FirstEthTxnProvider": "1.58180130245082",
    "FiveOrMoreGithubRepos": "1.63981424949996",
    "ForkedGithubRepoProvider": "1.60786863504348",
    "GitPOAP": "2.66960139522805",
    "GitcoinContributorStatistics#numGr14ContributionsGte#1": "1.62542471236007",
    "GitcoinContributorStatistics#numGrantsContributeToGte#1": "1.5667986894727",
    "GitcoinContributorStatistics#numGrantsContributeToGte#10": "1.51411296618984",
    "GitcoinContributorStatistics#numGrantsContributeToGte#100": "1.47827517188265",
    "GitcoinContributorStatistics#numGrantsContributeToGte#25": "1.44155616629543",
    "GitcoinContributorStatistics#numRoundsContributedToGte#1": "1.52589467397181",
    "GitcoinContributorStatistics#totalContributionAmountGte#10": "1.62200035378055",
    "GitcoinContributorStatistics#totalContributionAmountGte#100": "1.56181180203611",
    "GitcoinContributorStatistics#totalContributionAmountGte#1000": "1.79904899719317",
    "GitcoinGranteeStatistics#numGrantContributors#10": "1.84394852648612",
    "GitcoinGranteeStatistics#numGrantContributors#100": "2.26864939865892",
    "GitcoinGranteeStatistics#numGrantContributors#25": "2.08361979953084",
    "GitcoinGranteeStatistics#numGrantsInEcoAndCauseRound#1": "2.5622433792653",
    "GitcoinGranteeStatistics#numOwnedGrants#1": "2.60681697448028",
    "GitcoinGranteeStatistics#totalContributionAmount#100": "2.4437263427708",
    "GitcoinGranteeStatistics#totalContributionAmount#1000": "0.0714850845254669",
    "GitcoinGranteeStatistics#totalContributionAmount#10000": "0.486958916321513",
    "Github": "1.54275736194072",
    "GnosisSafe": "1.51067121350407",
    "Google": "1.52479089961097",
    "Lens": "1.64793579081762",
    "Linkedin": "1.63935238643971",
    "NFT": "1.57340924217419",
    "POAP": "1.62811354854131",
    "Poh": "1.63098291745772",
    "SelfStakingBronze": "2.5835503019261",
    "SelfStakingGold": "1.43099775341573",
    "SelfStakingSilver": "0.546306735288641",
    "SnapshotProposalsProvider": "1.50530735186189",
    "SnapshotVotesProvider": "1.59161056351538",
    "StarredGithubRepoProvider": "1.69015363582723",
    "TenOrMoreGithubFollowers": "1.55997767611887",
    "Twitter": "1.60034286168429",
    "TwitterFollowerGT100": "1.5865052692919",
    "TwitterFollowerGT500": "1.55220789860172",
    "TwitterFollowerGT5000": "1.50990658223365",
    "TwitterFollowerGTE1000": "1.61979117569772",
    "TwitterTweetGT10": "1.5771438230183",
    "ZkSync": "1.53450171160661",
    "ethPossessionsGte#1": "1.671345128954",
    "ethPossessionsGte#10": "2.59612446491527",
    "ethPossessionsGte#32": "1.50813577546905",
    "gtcPossessionsGte#10": "1.56064627302445",
    "gtcPossessionsGte#100": "1.64757125464823",
}

# The Boolean scorer deems Passport holders unique humans if they meet or exceed the below thresholdold
GITCOIN_PASSPORT_THRESHOLD = "21.11"
