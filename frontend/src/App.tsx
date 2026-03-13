import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Dashboard from "./app-pages/Dashboard";
import AdminDashboard from "./app-pages/AdminDashboard";
import PendingDevices from "./app-pages/PendingDevices";
import Marketplace from "./app-pages/Marketplace";
import MyModels from "./app-pages/MyModels";
import Playground from "./app-pages/Playground";
import Documents from "./app-pages/Documents";
import Mailbox from "./app-pages/Mailbox";
import Devices from "./app-pages/Devices";
import DeviceDetails from "./app-pages/DeviceDetails";
import DeviceSetup from "./app-pages/DeviceSetup";
import LinkDevices from "./app-pages/LinkDevices";
import Settings from "./app-pages/Settings";
import PolicyComparison from "./app-pages/PolicyComparison";
import PitchDeck from "./app-pages/PitchDeck";
import PodDashboard from "./app-pages/PodDashboard";
import Auth from "./app-pages/Auth";
import Signup from "./app-pages/Signup";
import NotFound from "./app-pages/NotFound";
import ElectronPlayground from "./app-pages/ElectronPlayground";
import Training from "./app-pages/Training";
import Workflows from "./app-pages/Workflows";
import AgentSchedules from "./app-pages/AgentSchedules";
import AgentWorkflows from "./app-pages/AgentWorkflows";
import ReviewQueue from "./app-pages/ReviewQueue";
import DeviceLinkConfirm from "./app-pages/DeviceLinkConfirm";



const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/electron-playground" element={<ElectronPlayground />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/device-link" element={<DeviceLinkConfirm />} />
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/admin" element={
                    <ProtectedRoute requireAdmin>
                      <AdminDashboard />
                    </ProtectedRoute>
                  } />
                  <Route path="/marketplace" element={<Marketplace />} />
                  <Route path="/my-models" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user", "viewer"]}>
                      <MyModels />
                    </ProtectedRoute>
                  } />
                  <Route path="/playground" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <Playground />
                    </ProtectedRoute>
                  } />
                  <Route path="/pod/:podId" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <PodDashboard />
                    </ProtectedRoute>
                  } />
                  <Route path="/documents" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <Documents />
                    </ProtectedRoute>
                  } />
                  <Route path="/mailbox" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <Mailbox />
                    </ProtectedRoute>
                  } />
                  <Route path="/devices" element={
                    <ProtectedRoute requireAdmin>
                      <Devices />
                    </ProtectedRoute>
                  } />
                  <Route path="/devices/pending" element={
                    <ProtectedRoute requireAdmin>
                      <PendingDevices />
                    </ProtectedRoute>
                  } />
                  <Route path="/devices/:id" element={
                    <ProtectedRoute requireAdmin>
                      <DeviceDetails />
                    </ProtectedRoute>
                  } />
                  <Route path="/device-setup" element={<DeviceSetup />} />
                  <Route path="/link-devices" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user", "viewer", "guest"]}>
                      <LinkDevices />
                    </ProtectedRoute>
                  } />
                  <Route path="/training" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <Training />
                    </ProtectedRoute>
                  } />
                  <Route path="/workflows" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <Workflows />
                    </ProtectedRoute>
                  } />
                  <Route path="/schedules" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <AgentSchedules />
                    </ProtectedRoute>
                  } />
                  <Route path="/agent-workflows" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <AgentWorkflows />
                    </ProtectedRoute>
                  } />
                  <Route path="/review-queue" element={
                    <ProtectedRoute allowedRoles={["global_admin", "admin", "user"]}>
                      <ReviewQueue />
                    </ProtectedRoute>
                  } />
                  
                  
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/pitch-deck" element={<PitchDeck />} />
                  {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
