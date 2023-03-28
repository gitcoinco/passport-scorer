import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { getCommunities, getApiKeys } from "../../utils/account-requests";

import { renderApp } from "../../__test-fixtures__/appHelpers";

jest.mock("../../utils/account-requests.ts", () => ({
  getCommunities: jest.fn(),
  getApiKeys: jest.fn(),
}));

describe("Page routing", () => {
  beforeEach(() => {
    (getCommunities as jest.Mock).mockResolvedValue([
      { name: "Test", description: "Test" },
    ]);
    (getApiKeys as jest.Mock).mockResolvedValue([]);
  });

  it("should render the scorer dashboard", async () => {
    const { getByText } = renderApp("/dashboard/scorer");

    await waitFor(() =>
      expect(getByText("Create a Scorer")).toBeInTheDocument()
    );
  });

  it("should show API key content when tab is clicked", async () => {
    const { getByText, getAllByText } = renderApp("/dashboard/scorer");

    const apiKeyElements = getAllByText("API Keys");
    expect(apiKeyElements.length).toBe(2);
    const apiKeyTab = apiKeyElements[1];

    fireEvent.click(apiKeyTab);

    await waitFor(() =>
      expect(getByText("Generate API Keys")).toBeInTheDocument()
    );
  });

  it("should show landing page at root path", async () => {
    const { getAllByText } = renderApp("/");

    await waitFor(() =>
      expect(getAllByText("Sign-in with Ethereum").length).toBeGreaterThan(0)
    );
  });

  it("should show 404 for missing path", async () => {
    const { getByText } = renderApp("/not/a/path");

    await waitFor(() =>
      expect(getByText("404 - Page Not Found")).toBeInTheDocument()
    );
  });
});
