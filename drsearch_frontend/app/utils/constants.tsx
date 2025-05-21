// app\utils\constants.tsx

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8011";

/** Central place for UI text and links used across the frontend */
export const UI = {
  assistantTitle: process.env.NEXT_PUBLIC_ASSISTANT_TITLE ?? "DRS ASSISTANT",
  inputPlaceholder:
    process.env.NEXT_PUBLIC_INPUT_PLACEHOLDER ?? "How do I send a ticket to IT",
  assistantTagline: "Your DRS Assistant",
  emptyStateTagline: "Here to assist",
  selectIndexPlaceholder: "Select Document Index",
  homePageLinkText: "View AIS‑FWB Home Page",
  homePageLinkUrl:
    "https://www.leonardodrs.com/locations/airborne-intelligence-systems-fort-walton-beach/",
  iconSrc: "llama_cafe.ico",
  signInButton: "Sign in",
  settingsTitle: "Settings",
  settingsDocsLabel: "Documents to retrieve",
  openSettingsAriaLabel: "Open settings",
  sourcesHeader: "Sources",
  answerHeader: "Answer",
  feedbackAlreadyGiven: "You have already provided your feedback.",
  traceButtonText: "🚀🚀 View trace",
  unableToViewTrace: "Unable to view trace",
  unknownDocument: "Unknown Document",
};
