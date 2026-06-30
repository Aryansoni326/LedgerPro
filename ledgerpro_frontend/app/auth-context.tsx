'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

interface User {
  email: string;
  name: string;
  avatar?: string;
}

export interface Firm {
  id: number;
  name: string;
  gstin?: string;
  state: string;
  city: string;
  owner_email: string;
  status: 'pending_verification' | 'active';
  created_at: string;
}

interface AuthContextProps {
  user: User | null;
  token: string | null;
  loading: boolean;
  firms: Firm[];
  selectedFirm: Firm | null;
  fetchFirms: () => Promise<void>;
  setSelectedFirm: (firm: Firm | null) => void;
  loginWithGoogleToken: (googleToken: string) => Promise<{ pending_2fa: boolean; pending_token?: string; email?: string }>;
  verifyOTPCode: (pendingToken: string, code: string) => Promise<void>;
  resendOTPCode: (pendingToken: string) => Promise<string>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [firms, setFirms] = useState<Firm[]>([]);
  const [selectedFirm, setSelectedFirmState] = useState<Firm | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Restore session on client mount
    const savedToken = localStorage.getItem('auth_token');
    const savedUser = localStorage.getItem('auth_user');

    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  // Fetch firms when token changes
  useEffect(() => {
    if (token) {
      fetchFirms();
    } else {
      setFirms([]);
      setSelectedFirmState(null);
    }
  }, [token]);

  // Route gating hook
  useEffect(() => {
    if (loading) return;

    const publicRoutes = ['/login', '/verify-otp'];
    const isDashboardRoute = pathname?.startsWith('/dashboard');

    if (isDashboardRoute && !token) {
      router.push('/login');
    } else if (token && publicRoutes.includes(pathname)) {
      router.push('/dashboard');
    }
  }, [token, pathname, loading, router]);

  const fetchFirms = async () => {
    const activeToken = token || localStorage.getItem('auth_token');
    if (!activeToken) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms`, {
        method: 'GET',
        headers: { 
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        },
      });
      if (res.ok) {
        const data = await res.json();
        setFirms(data);
        
        // Auto select firm if stored
        const savedFirmId = localStorage.getItem('selected_firm_id');
        if (savedFirmId) {
          const firm = data.find((f: Firm) => f.id === parseInt(savedFirmId));
          if (firm) {
            setSelectedFirmState(firm);
          } else {
            setSelectedFirmState(null);
          }
        } else if (data.length > 0) {
          // Default to first active firm if none saved
          const firstActive = data.find((f: Firm) => f.status === 'active');
          if (firstActive) {
            setSelectedFirmState(firstActive);
            localStorage.setItem('selected_firm_id', firstActive.id.toString());
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch firms:", err);
    }
  };

  const setSelectedFirm = (firm: Firm | null) => {
    setSelectedFirmState(firm);
    if (firm) {
      localStorage.setItem('selected_firm_id', firm.id.toString());
    } else {
      localStorage.removeItem('selected_firm_id');
    }
  };

  const loginWithGoogleToken = async (googleToken: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${apiUrl}/api/auth/google/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential: googleToken }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Google callback failed');
    }

    return {
      pending_2fa: true,
      pending_token: data.pending_2fa_token,
      email: data.email
    };
  };

  const verifyOTPCode = async (pendingToken: string, code: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${apiUrl}/api/auth/otp/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken, code }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Verification failed');
    }

    // Save session details
    localStorage.setItem('auth_token', data.token);
    localStorage.setItem('auth_user', JSON.stringify(data.user));
    
    setToken(data.token);
    setUser(data.user);
    
    router.push('/dashboard');
  };

  const resendOTPCode = async (pendingToken: string): Promise<string> => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${apiUrl}/api/auth/otp/resend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Resend request failed');
    }

    return data.pending_2fa_token;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('selected_firm_id');
    setToken(null);
    setUser(null);
    setFirms([]);
    setSelectedFirmState(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        firms,
        selectedFirm,
        fetchFirms,
        setSelectedFirm,
        loginWithGoogleToken,
        verifyOTPCode,
        resendOTPCode,
        logout,
        isAuthenticated: !!token
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
