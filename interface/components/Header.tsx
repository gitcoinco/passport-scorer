// --- React methods
import React, { useContext, useEffect, useMemo } from "react";
import { UserContext } from "../context/userContext";
import {
  PAGE_PADDING,
  CONTENT_MAX_WIDTH_INCLUDING_PADDING,
} from "./PageLayout";
import Warning from "./Warning";
import MinimalHeader from "./MinimalHeader";

type HeaderProps = {
  subheader?: React.ReactNode;
};

const Header = ({ subheader }: HeaderProps): JSX.Element => {
  const { userWarning, setUserWarning } = useContext(UserContext);

  return (
    <div className={"border-b border-gray-300 bg-white"}>
      <div className={`w-full bg-white ${PAGE_PADDING}`}>
        <MinimalHeader
          className={`${subheader ? "border-b border-b-gray-200" : ""}`}
        />
      </div>
      <div className={`w-full bg-red-100 ${PAGE_PADDING}`}>
        {userWarning && (
          <Warning text={userWarning} onDismiss={() => setUserWarning()} />
        )}
      </div>
      <div
        className={`mx-auto w-full ${PAGE_PADDING} ${CONTENT_MAX_WIDTH_INCLUDING_PADDING}`}
      >
        {subheader}
      </div>
    </div>
  );
};

export default Header;
