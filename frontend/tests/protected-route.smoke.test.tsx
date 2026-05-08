import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useUserRole } from "@/hooks/useUserRole";

vi.mock("@/hooks/useUserRole", () => ({
  useUserRole: vi.fn(),
}));

describe("ProtectedRoute smoke", () => {
  it("redirects unauthenticated users to /auth", () => {
    vi.mocked(useUserRole).mockReturnValue({
      role: null,
      user: null,
      isAuthenticated: false,
      loading: false,
      isAdmin: false,
      isUser: false,
    });

    render(
      <MemoryRouter initialEntries={["/private"]}>
        <Routes>
          <Route path="/auth" element={<div>AuthPage</div>} />
          <Route
            path="/private"
            element={
              <ProtectedRoute>
                <div>PrivatePage</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("AuthPage")).toBeInTheDocument();
  });

  it("allows admin-only route for admin role", () => {
    vi.mocked(useUserRole).mockReturnValue({
      role: "admin",
      user: { id: "123" } as any,
      isAuthenticated: true,
      loading: false,
      isAdmin: true,
      isUser: false,
    });

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/" element={<div>HomePage</div>} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <div>AdminPage</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("AdminPage")).toBeInTheDocument();
  });

  it("redirects non-admin from admin route", () => {
    vi.mocked(useUserRole).mockReturnValue({
      role: "user",
      user: { id: "123" } as any,
      isAuthenticated: true,
      loading: false,
      isAdmin: false,
      isUser: true,
    });

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/" element={<div>HomePage</div>} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <div>AdminPage</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("HomePage")).toBeInTheDocument();
  });
});
