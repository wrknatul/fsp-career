/// <reference types="vite/client" />

// Build-time variables used by the app (all optional, see src/utils/demo.ts):
//   VITE_DEMO_MODE            'false' hides the one-click demo login buttons
//   VITE_DEMO_CANDIDATE_EMAIL demo candidate e-mail override
//   VITE_DEMO_EMPLOYER_EMAIL  demo employer e-mail override
//   VITE_DEMO_PASSWORD        demo password override
// They are read with typeof checks; ImportMetaEnv is deliberately not augmented
// (the project keeps `type` aliases only, and augmenting that global needs another declaration form).
