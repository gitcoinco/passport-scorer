Feature: Retrieve logged Passport scores for Ethereum addresses within a community

As a developer using the API, I want to be able to read the logged Passport scores of multiple Ethereum addresses within a community that I manage, so that I can efficiently retrieve this information for my users.

Scenario: Retrieve logged Passport scores for Ethereum addresses within a community
  Given a list of Ethereum addresses and a community managed by the developer using the API
  When the developer makes a request to the API to retrieve the logged Passport scores for the Ethereum addresses within the specified community
  Then the API should return the logged Passport scores for each Ethereum address in the list in a format that is easy to work with (e.g. a JSON object)
  And the API should handle errors and return appropriate messages if any of the Ethereum addresses are invalid or if there are issues with the request.
