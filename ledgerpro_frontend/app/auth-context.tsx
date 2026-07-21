'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getApiBaseUrl } from './lib/api-url';

interface User {
  email: string;
  name: string;
  avatar?: string;
  role?: string;
  access_mode?: 'full' | 'read_only';
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
  access_mode?: 'full' | 'read_only';
  accountant_email?: string;
}

interface AuthContextProps {
  user: User | null;
  token: string | null;
  loading: boolean;
  firms: Firm[];
  selectedFirm: Firm | null;
  accessMode: 'full' | 'read_only';
  isReadOnly: boolean;
  fetchFirms: () => Promise<void>;
  setSelectedFirm: (firm: Firm | null) => void;
  initiateGoogleLogin: () => void;
  loginWithGoogleCode: (code: string) => Promise<{ pending_2fa: boolean; pending_token?: string; email?: string }>;
  loginWithEmail: (email: string) => Promise<{ pending_2fa: boolean; pending_token?: string; email?: string }>;
  loginAsOwner: (email: string) => Promise<{ pending_2fa: boolean; pending_token?: string; email?: string }>;
  verifyOTPCode: (pendingToken: string, code: string) => Promise<void>;
  resendOTPCode: (pendingToken: string) => Promise<string>;
  logout: () => void;
  isAuthenticated: boolean;
  registerWithGoogle: () => void;
  registerWithGoogleCode: (code: string) => Promise<{ registration_token: string; email: string; name: string; avatar?: string }>;
  registerWithEmail: (email: string) => Promise<{ registration_token: string; email: string; pending_2fa_token: string }>;
  completeProfile: (data: { registration_token: string; name: string; phone_number: string; pan_number?: string; role: string; location?: string; organization?: string }) => Promise<{ pending_2fa_token: string; email: string }>;
  updateUser: (updatedUser: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextProps | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [firms, setFirms] = useState<Firm[]>([]);
  const [selectedFirm, setSelectedFirmState] = useState<Firm | null>(null);
  const [accessMode, setAccessMode] = useState<'full' | 'read_only'>('full');
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const savedToken = localStorage.getItem('auth_token');
    const savedUser = localStorage.getItem('auth_user');
    const savedMode = localStorage.getItem('auth_access_mode') as 'full' | 'read_only' | null;
    try {
      if (savedToken && savedUser) {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
        setAccessMode(savedMode === 'read_only' ? 'read_only' : 'full');
      }
    } catch (e) {
      console.error('Failed to parse saved auth session:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_access_mode');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (token) {
      fetchFirms();
    } else {
      setFirms([]);
      setSelectedFirmState(null);
    }
  }, [token]);

  useEffect(() => {
    if (loading) return;
    const publicRoutes = ['/login', '/verify-otp', '/register', '/owner/login'];
    const isDashboardRoute = pathname?.startsWith('/dashboard');
    if (isDashboardRoute && !token) {
      router.push('/login');
    } else if (token && publicRoutes.includes(pathname || '')) {
      router.push('/dashboard');
    }
  }, [token, pathname, loading, router]);

  const fetchFirms = async () => {
    const activeToken = token || localStorage.getItem('auth_token');
    if (!activeToken) return;
    const apiUrl = getApiBaseUrl();
    try {
      const res = await fetch(`${apiUrl}/api/firms`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${activeToken}`,
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setFirms(data);
        const savedFirmId = localStorage.getItem('selected_firm_id');
        if (savedFirmId) {
          const firm = data.find((f: Firm) => f.id === parseInt(savedFirmId));
          if (firm) setSelectedFirmState(firm);
          else setSelectedFirmState(null);
        } else if (data.length > 0) {
          const firstActive = data.find((f: Firm) => f.status === 'active');
          if (firstActive) {
            setSelectedFirmState(firstActive);
            localStorage.setItem('selected_firm_id', firstActive.id.toString());
          }
        }
      } else if (res.status === 401 || res.status === 403) {
        logout();
      }
    } catch (err) {
      console.error('Failed to fetch firms:', err);
    }
  };

  const setSelectedFirm = (firm: Firm | null) => {
    setSelectedFirmState(firm);
    if (firm) localStorage.setItem('selected_firm_id', firm.id.toString());
    else localStorage.removeItem('selected_firm_id');
  };

  const initiateGoogleLogin = () => {
    const apiUrl = getApiBaseUrl();
    window.location.href = `${apiUrl}/api/auth/google/initiate?flow=login`;
  };

  const loginWithGoogleCode = async (code: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/google/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Google login failed');
    return {
      pending_2fa: true,
      pending_token: data.pending_2fa_token,
      email: data.email,
    };
  };

  const loginWithEmail = async (email: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/email/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Email login failed');
    return {
      pending_2fa: true,
      pending_token: data.pending_2fa_token,
      email: data.email,
    };
  };

  const loginAsOwner = async (email: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/owner/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Owner login failed');
    return {
      pending_2fa: true,
      pending_token: data.pending_2fa_token,
      email: data.email,
    };
  };

  const verifyOTPCode = async (pendingToken: string, code: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/otp/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken, code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Verification failed');

    const mode: 'full' | 'read_only' =
      data.access_mode === 'read_only' || data.user?.access_mode === 'read_only'
        ? 'read_only'
        : 'full';

    localStorage.setItem('auth_token', data.token);
    localStorage.setItem('auth_user', JSON.stringify(data.user));
    localStorage.setItem('auth_access_mode', mode);
    sessionStorage.removeItem('pending_2fa_token');
    sessionStorage.removeItem('pending_email');
    sessionStorage.removeItem('auth_flow');
    setToken(data.token);
    setUser(data.user);
    setAccessMode(mode);
    router.push('/dashboard');
  };

  const resendOTPCode = async (pendingToken: string): Promise<string> => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/otp/resend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Resend request failed');
    return data.pending_2fa_token;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_access_mode');
    localStorage.removeItem('selected_firm_id');
    setToken(null);
    setUser(null);
    setAccessMode('full');
    setFirms([]);
    setSelectedFirmState(null);
    router.push('/');
  };

  const registerWithGoogle = () => {
    sessionStorage.setItem('auth_flow', 'register');
    const apiUrl = getApiBaseUrl();
    window.location.href = `${apiUrl}/api/auth/google/initiate?flow=register`;
  };

  const registerWithGoogleCode = async (code: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/register/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Registration failed');
    return data;
  };

  const registerWithEmail = async (email: string) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/register/email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Registration failed');
    return data;
  };

  const completeProfile = async (profileData: { registration_token: string; name: string; phone_number: string; pan_number?: string; role: string; location?: string; organization?: string }) => {
    const apiUrl = getApiBaseUrl();
    const res = await fetch(`${apiUrl}/api/auth/register/complete-profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Profile completion failed');
    return data;
  };

  const updateUser = (updatedFields: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return null;
      const nextUser = { ...prev, ...updatedFields };
      localStorage.setItem('auth_user', JSON.stringify(nextUser));
      return nextUser;
    });
  };

  const firmReadOnly = selectedFirm?.access_mode === 'read_only';
  const isReadOnly = accessMode === 'read_only' || firmReadOnly;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        firms,
        selectedFirm,
        accessMode,
        isReadOnly,
        fetchFirms,
        setSelectedFirm,
        initiateGoogleLogin,
        loginWithGoogleCode,
        loginWithEmail,
        loginAsOwner,
        verifyOTPCode,
        resendOTPCode,
        logout,
        isAuthenticated: !!token,
        registerWithGoogle,
        registerWithGoogleCode,
        registerWithEmail,
        completeProfile,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
