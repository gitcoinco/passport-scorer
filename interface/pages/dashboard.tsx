// // --- React components/methods
// import React, { useState } from "react";

// // --- Wagmi
// // import { useAccount, useConnect } from "wagmi";

// // --- Components
// import Header from "../components/Header";
// import CommunityList from "../components/CommunityList";
// import { SettingsIcon, Icon } from "@chakra-ui/icons";
// import { GoInbox } from "react-icons/go"

// // --- Types
// import { AuthenticationStatus } from "@rainbow-me/rainbowkit";
// import { ApiKeyList } from "../components/APIKeyList";

// type DashboardProps = {
//   // setAuthenticationStatus?: Function;
//   authenticationStatus: AuthenticationStatus;
// };

// export default function Dashboard({
//   // setAuthenticationStatus,
//   authenticationStatus,
// }: DashboardProps) {
//   const [activeTab, setActiveTab] = useState("communities");

//   /**
//    * @TODO
//    * --> if user has communities, show them the "Create key" button in the top part of the page
//    */

//   const tabbedClasses = (tab: string) => {
//     const base = "my-4 flex leading-4 cursor-pointer";
//     return tab === activeTab ? `${base} font-bold font-blue-darkblue` : `${base} text-purple-softpurple`;
//   };

//   return (
//     <>
//       <div>
//         <Header authenticationStatus={authenticationStatus} />
//         <div>
//           <div className="mt-0 w-full border-b border-gray-300 p-6 pb-6 text-black">
//             <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
//               Dashboard
//             </h1>
//             <p className="mt-2 font-librefranklin text-purple-softpurple">
//               Generate community IDs for specific applications using
//               non-duplication rules like first-in-first-out or
//               last-in-first-out.
//             </p>
//           </div>
//           <div className="flex bg-gray-bluegray px-6">
//             <div className="my-4 min-h-full w-1/5 flex-col border-r border-gray-lightgray">
//               <button
//                 data-testid="communities-tab"
//                 onClick={() => setActiveTab("communities")}
//                 className={tabbedClasses("communities")}
//               >
//                 <Icon as={GoInbox} className="mr-2" />Communities
//               </button>
//               <button
//                 data-testid="api-keys-tab"
//                 onClick={() => setActiveTab("apiKeys")}
//                 className={tabbedClasses("apiKeys")}
//               >
//                 <SettingsIcon className="mr-2" /> API Keys
//               </button>
//             </div>
//             <div className="flex min-h-full w-full flex-col p-6 md:h-screen">
//               {activeTab === "communities" ? <CommunityList /> : <ApiKeyList />}
//             </div>
//           </div>
//         </div>
//       </div>
//     </>
//   );
// }
