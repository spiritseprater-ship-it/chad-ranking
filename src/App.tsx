import { Route, Routes } from 'react-router-dom'
import { RootLayout } from '@/layouts/RootLayout'
import { AdminLayout } from '@/layouts/AdminLayout'
import { RequireAuth } from '@/components/auth/Guards'
import { HomePage } from '@/pages/HomePage'
import { SignUpPage } from '@/pages/SignUpPage'
import { LoginPage } from '@/pages/LoginPage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { SubmitPage } from '@/pages/SubmitPage'
import { SubmitResultPage } from '@/pages/SubmitResultPage'
import { ShowcaseSetupPage } from '@/pages/ShowcaseSetupPage'
import { LeaderboardPage } from '@/pages/LeaderboardPage'
import { ParticipantsPage } from '@/pages/ParticipantsPage'
import { ProfilePage, OwnProfileRedirect } from '@/pages/ProfilePage'
import { AdminDashboardPage } from '@/pages/AdminDashboardPage'
import { AdminUsersPage } from '@/pages/AdminUsersPage'
import { AdminModerationPage } from '@/pages/AdminModerationPage'
import { AdminAuditPage } from '@/pages/AdminAuditPage'
import { RulesPage } from '@/pages/RulesPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function App() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route index element={<HomePage />} />
        <Route path="signup" element={<SignUpPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="leaderboard" element={<LeaderboardPage />} />
        <Route path="participants" element={<ParticipantsPage />} />
        <Route path="rules" element={<RulesPage />} />
        <Route path="profile" element={<RequireAuth><OwnProfileRedirect /></RequireAuth>} />
        <Route path="profile/:username" element={<ProfilePage />} />
        <Route
          path="dashboard"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="submit"
          element={
            <RequireAuth>
              <SubmitPage />
            </RequireAuth>
          }
        />
        <Route
          path="submit/result"
          element={
            <RequireAuth>
              <SubmitResultPage />
            </RequireAuth>
          }
        />
        <Route
          path="showcase"
          element={
            <RequireAuth>
              <ShowcaseSetupPage />
            </RequireAuth>
          }
        />
        <Route path="admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboardPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="moderation" element={<AdminModerationPage />} />
          <Route path="audit" element={<AdminAuditPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
