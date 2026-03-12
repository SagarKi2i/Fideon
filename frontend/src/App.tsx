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
import Settings from "./app-pages/Settings";
import PolicyComparison from "./app-pages/PolicyComparison";
import PitchDeck from "./app-pages/PitchDeck";
import PodDashboard from "./app-pages/PodDashboard";
import Auth from "./app-pages/Auth";
import NotFound from "./app-pages/NotFound";
import ElectronPlayground from "./app-pages/ElectronPlayground";
import Training from "./app-pages/Training";
import Workflows from "./app-pages/Workflows";
import AgentSchedules from "./app-pages/AgentSchedules";
import AgentWorkflows from "./app-pages/AgentWorkflows";
import ReviewQueue from "./app-pages/ReviewQueue";



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
                  <Route path="/my-models" element={<MyModels />} />
                  <Route path="/playground" element={<Playground />} />
                  <Route path="/pod/:podId" element={<PodDashboard />} />
                  <Route path="/documents" element={<Documents />} />
                  <Route path="/mailbox" element={<Mailbox />} />
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
                  <Route path="/training" element={<Training />} />
                  <Route path="/workflows" element={<Workflows />} />
                  <Route path="/schedules" element={<AgentSchedules />} />
                  <Route path="/agent-workflows" element={<AgentWorkflows />} />
                  <Route path="/review-queue" element={<ReviewQueue />} />
                  
                  
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
