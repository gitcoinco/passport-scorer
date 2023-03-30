// --- React Methods
import React, { useContext, useEffect, useRef } from "react";
import {
  HashRouter as Router,
  Routes,
  Route,
  redirect,
} from "react-router-dom";
import RequireAuth from "../components/RequireAuth";

// --- Components
import Dashboard from "../components/Dashboard";
import CommunityList from "../components/CommunityList";
import APIKeyList from "../components/APIKeyList";
import NewScorer from "../components/NewScorer";
import LandingPage from "../components/LandingPage";

// --- Context
import { UserContext } from "../context/userContext";
import { useToast, ToastId } from "@chakra-ui/react";

import PageLayout from "../components/PageLayout";
import HomePageLayout from "../components/HomePageLayout";
import NoMatch from "../components/NoMatch";
import { useClickOutsideToast } from "../components/useClickOutsideToast";

// Layout Route pattern from https://reactrouter.com/en/main/start/concepts#layout-routes
export const PageRoutes = () => (
  <Routes>
    <Route element={<HomePageLayout />}>
      <Route path="/" element={<LandingPage />} />
    </Route>
    <Route element={<PageLayout />}>
      <Route path="/dashboard" element={<Dashboard />}>
        <Route path="/dashboard/scorer" element={<CommunityList />} />
        <Route path="/dashboard/api-keys" element={<APIKeyList />} />
      </Route>
      <Route path="/new-scorer" element={<NewScorer />} />
    </Route>
    <Route path="*" element={<NoMatch />} />
  </Routes>
);

const PageRouter = () => {
  const { loginComplete } = useContext(UserContext);
  const { openToast } = useClickOutsideToast();

  useEffect(() => {
    if (loginComplete) {
      openToast({
        duration: null,
        isClosable: true,
        render: (result: any) => (
          <div style={{
            marginBottom: "80px"
          }} className="flex justify-between rounded-md bg-blue-darkblue p-4 text-white">
            <span className="step-icon step-icon-completed flex h-9 items-center">
              <span className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-teal-600">
                <img
                  alt="completed icon"
                  className="sticky top-0 h-6"
                  src="/assets/white-check-icon.svg"
                />
              </span>
            </span>
            <p className="py-1 px-3">Ethereum account has been validated.</p>
            <button className="sticky top-0" onClick={result.onClose}>
              <img
                alt="close button"
                className="rounded-lg hover:bg-gray-500"
                src="/assets/x-icon.svg"
              />
            </button>
          </div>
        ),
      });
    }
  }, [loginComplete]);

  return (
    <Router>
      <RequireAuth>
        <PageRoutes />
      </RequireAuth>
    </Router>
  );
};

export default PageRouter;
