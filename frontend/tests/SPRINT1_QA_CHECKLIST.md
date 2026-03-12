# Sprint 1 QA Checklist (Excluding FNF-14)

## Authentication
- [ ] Email sign-in works with valid credentials.
- [ ] Invalid credentials show error toast.
- [ ] Forgot-password flow sends reset email.
- [ ] Recovery link opens `/auth` and allows password reset.
- [ ] Post-login redirect sends admins to `/admin`, users to `/`.
- [ ] Protected routes redirect unauthenticated users to `/auth`.

## SSO and MFA Scaffolding
- [ ] SSO buttons are visible only when `NEXT_PUBLIC_AUTH_ENABLE_SSO=true`.
- [ ] Enabled providers follow `NEXT_PUBLIC_AUTH_SSO_PROVIDERS`.
- [ ] MFA panel is visible only when `NEXT_PUBLIC_AUTH_ENABLE_MFA=true`.
- [ ] MFA enroll/challenge/verify/unenroll controls function with Supabase config.

## Dashboard Scaffold
- [ ] Admin dashboard renders metrics cards and actions.
- [ ] User dashboard renders active pods and empty-state fallback.
- [ ] Non-admin user cannot open admin-only pages.

## Responsive and Accessibility
- [ ] Auth page is usable on mobile (<768px), tablet, and desktop.
- [ ] Keyboard-only navigation works for auth controls.
- [ ] Inputs have labels and buttons have accessible names.
- [ ] Focus states are visible for interactive controls.

## Smoke Commands
- [ ] `npm run lint`
- [ ] `npm run test:run`
- [ ] `npm run build`
