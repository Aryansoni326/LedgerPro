'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth, Firm } from '../auth-context';
import { useTheme } from '../providers';
import AddFirmModal from '../components/add-firm-modal';
import SaasFooter from '../components/saas-footer';
import DashboardNav, { TabType } from '../components/dashboard-nav';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts';
import { 
  Building, 
  Plus, 
  Moon, 
  Sun, 
  LogOut, 
  FileText, 
  Globe, 
  Truck, 
  ChevronDown,
  Upload,
  AlertCircle,
  FileCheck,
  UserCheck,
  FolderOpen,
  X,
  File,
  Loader2,
  CheckCircle2,
  Clock,
  Edit2,
  RefreshCw,
  Info,
  TrendingUp,
  TrendingDown,
  BarChart2,
  Calendar,
  Menu
} from 'lucide-react';

export default function DashboardPage() {
  const { token, user, logout, loading: authLoading, firms, selectedFirm, setSelectedFirm } = useAuth();
  const { theme, toggleTheme, mounted } = useTheme();
  
  // Tab and dropdown states
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [invoiceType, setInvoiceType] = useState<'purchase' | 'sales'>('purchase');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Invoices & Upload states
  const [bills, setBills] = useState<any[]>([]);
  const [isLoadingBills, setIsLoadingBills] = useState(false);
  const [isInitialBillsLoad, setIsInitialBillsLoad] = useState(true);
  const [toasts, setToasts] = useState<{ id: string; message: string }[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<any[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [summaryMessage, setSummaryMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Spreadsheets inline editing states
  const [editingCell, setEditingCell] = useState<{ billId: number; field: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [includeUnverified, setIncludeUnverified] = useState(false);

  // Search, Filters & Action Modals
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [billTypeFilter, setBillTypeFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [viewingBill, setViewingBill] = useState<any | null>(null);
  const [deletingBillId, setDeletingBillId] = useState<number | null>(null);
  const [exportBatch, setExportBatch] = useState<any | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [verifyingBillId, setVerifyingBillId] = useState<number | null>(null);
  const [retryingBillId, setRetryingBillId] = useState<number | null>(null);
  const [isDeletingBill, setIsDeletingBill] = useState(false);
  const [savingBillId, setSavingBillId] = useState<number | null>(null);
  const [savingTradeDocId, setSavingTradeDocId] = useState<number | null>(null);

  const getFileUrl = (url: string) => {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return `${apiUrl}${url}`;
  };

  // Vault States
  const [vaultYears, setVaultYears] = useState<number[]>([]);
  const [vaultMonths, setVaultMonths] = useState<number[]>([]);
  const [vaultDays, setVaultDays] = useState<number[]>([]);
  const [vaultFiles, setVaultFiles] = useState<any[]>([]);
  const [selectedVaultYear, setSelectedVaultYear] = useState<number | null>(null);
  const [selectedVaultMonth, setSelectedVaultMonth] = useState<number | null>(null);
  const [selectedVaultDay, setSelectedVaultDay] = useState<number | null>(null);
  const [vaultModuleFilter, setVaultModuleFilter] = useState<string>('');
  const [isLoadingVault, setIsLoadingVault] = useState(false);
  const [deletingVaultEntryId, setDeletingVaultEntryId] = useState<number | null>(null);

  // Analytics States
  const [analyticsRange, setAnalyticsRange] = useState<'month' | 'quarter' | 'year'>('year');
  const [analyticsSummary, setAnalyticsSummary] = useState<any | null>(null);
  const [analyticsTurnover, setAnalyticsTurnover] = useState<any[]>([]);
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState(false);

  // Import-Export (Trade Docs) States
  const [tradeDocs, setTradeDocs] = useState<any[]>([]);
  const [isLoadingTradeDocs, setIsLoadingTradeDocs] = useState(false);
  const [isRefreshingTradeDocs, setIsRefreshingTradeDocs] = useState(false);
  const [isInitialTradeDocsLoad, setIsInitialTradeDocsLoad] = useState(true);
  const [verifyingTradeDocId, setVerifyingTradeDocId] = useState<number | null>(null);
  const [retryingTradeDocId, setRetryingTradeDocId] = useState<number | null>(null);
  const [isDeletingTradeDoc, setIsDeletingTradeDoc] = useState(false);
  const [isStubUploading, setIsStubUploading] = useState(false);
  const [tradeDocUploadingFiles, setTradeDocUploadingFiles] = useState<any[]>([]);
  const [tradeDocSummaryMsg, setTradeDocSummaryMsg] = useState('');
  const [tradeDocSearch, setTradeDocSearch] = useState('');
  const [tradeDocStatusFilter, setTradeDocStatusFilter] = useState('');
  const [viewingTradeDoc, setViewingTradeDoc] = useState<any | null>(null);
  const [deletingTradeDocId, setDeletingTradeDocId] = useState<number | null>(null);
  const [editingTradeCell, setEditingTradeCell] = useState<{ docId: number; field: string } | null>(null);
  const [editTradeValue, setEditTradeValue] = useState('');
  const [isDraggingTrade, setIsDraggingTrade] = useState(false);
  const tradeDocInputRef = useRef<HTMLInputElement>(null);

  const importExportInputRef = useRef<HTMLInputElement>(null);
  const ewayBillsInputRef = useRef<HTMLInputElement>(null);


  // Form states for settings panel
  const [accountantName, setAccountantName] = useState(user?.name || '');
  const [geminiKey, setGeminiKey] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  // 1. Toast Notification Trigger
  const triggerToast = (message: string) => {
    const id = Math.random().toString();
    setToasts((prev) => [...prev, { id, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  // 2. Fetch Invoices List
  const fetchBills = async (options?: { silent?: boolean }) => {
    const activeToken = token || localStorage.getItem('auth_token');
    if (!activeToken || !selectedFirm) return;
    if (!options?.silent) setIsLoadingBills(true);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    const queryParams = new URLSearchParams();
    if (searchQuery) queryParams.append('search', searchQuery);
    if (statusFilter) queryParams.append('status', statusFilter);
    if (billTypeFilter) queryParams.append('bill_type', billTypeFilter);
    if (startDate) queryParams.append('start_date', startDate);
    if (endDate) queryParams.append('end_date', endDate);

    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/invoices?${queryParams.toString()}`, {
        headers: { 
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        const data = await res.json();
        
        // Check for state transitions from 'processing' to 'needs_review' to alert user
        setBills((prevBills) => {
          if (prevBills.length > 0) {
            data.forEach((newBill: any) => {
              const oldBill = prevBills.find((b: any) => b.id === newBill.id);
              if (oldBill && oldBill.status === 'processing' && newBill.status === 'needs_review') {
                triggerToast(`Invoice "${newBill.file_name}" completed processing and is ready for review.`);
              }
            });
          }
          return data;
        });
      }
    } catch (err) {
      console.error("Failed to fetch bills:", err);
    } finally {
      setIsLoadingBills(false);
      setIsInitialBillsLoad(false);
    }
  };

  // 3. Polling & Filtering Effect
  useEffect(() => {
    if (!selectedFirm) return;
    fetchBills();

    // Poll every 3.5 seconds
    const interval = setInterval(() => {
      fetchBills({ silent: true });
    }, 3500);

    return () => clearInterval(interval);
  }, [selectedFirm, searchQuery, statusFilter, billTypeFilter, startDate, endDate, activeTab]);

  // Reset initial load flags when firm changes
  useEffect(() => {
    if (selectedFirm) {
      setIsInitialBillsLoad(true);
      setIsInitialTradeDocsLoad(true);
    }
  }, [selectedFirm?.id]);

  // Vault Initializer Effect
  useEffect(() => {
    if (activeTab === 'vault' && selectedFirm) {
      fetchVaultYears();
      setSelectedVaultYear(null);
      setSelectedVaultMonth(null);
      setSelectedVaultDay(null);
      setVaultFiles([]);
    }
  }, [activeTab, selectedFirm]);

  // Analytics Fetch
  const fetchAnalytics = async (range: string) => {
    if (!selectedFirm) return;
    setIsLoadingAnalytics(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const [summaryRes, turnoverRes] = await Promise.all([
        fetch(`${apiUrl}/api/firms/${selectedFirm.id}/analytics/summary?range=${range}`, {
          headers: { 'Authorization': `Bearer ${activeToken}` }
        }),
        fetch(`${apiUrl}/api/firms/${selectedFirm.id}/analytics/turnover?range=${range}`, {
          headers: { 'Authorization': `Bearer ${activeToken}` }
        })
      ]);
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setAnalyticsSummary(data);
      }
      if (turnoverRes.ok) {
        const data = await turnoverRes.json();
        setAnalyticsTurnover(data);
      }
    } catch (err) {
      console.error('Analytics fetch failed:', err);
    } finally {
      setIsLoadingAnalytics(false);
    }
  };

  // Analytics Initializer Effect
  useEffect(() => {
    if (activeTab === 'overview' && selectedFirm) {
      fetchAnalytics(analyticsRange);
    }
  }, [activeTab, selectedFirm, analyticsRange]);

  // 3.5. Delete Invoice Handler

  const handleDeleteBill = async (billId: number) => {
    setIsDeletingBill(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${billId}`, {
        method: 'DELETE',
        headers: { 
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        setBills((prev) => prev.filter((b) => b.id !== billId));
        triggerToast("Invoice soft-deleted successfully.");
      } else {
        triggerToast("Failed to delete invoice.");
      }
    } catch (err) {
      triggerToast("Connection error during delete.");
    } finally {
      setIsDeletingBill(false);
    }
  };
  const handleGenerateExcel = async () => {
    if (!selectedFirm) return;
    setIsExporting(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/invoices/export-excel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          status: statusFilter || undefined,
          bill_type: billTypeFilter || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          include_unverified: includeUnverified
        })
      });

      if (res.ok) {
        const batch = await res.json();
        setExportBatch(batch);
        triggerToast("Excel sheet generated successfully!");
      } else {
        const data = await res.json();
        triggerToast(data.error || "Failed to generate Excel.");
      }
    } catch (err) {
      triggerToast("Connection failed during export.");
    } finally {
      setIsExporting(false);
    }
  };

  // 3.7. Download Export Handler
  const handleDownloadExport = (url: string, name: string) => {
    const link = document.createElement('a');
    link.href = getFileUrl(url);
    link.setAttribute('download', name);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setExportBatch(null);
  };

  // 3.8. Vault Helpers & Handlers
  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  const getMonthName = (num: number) => {
    return monthNames[num - 1] || `Month ${num}`;
  };

  const fetchVaultYears = async () => {
    if (!selectedFirm) return;
    setIsLoadingVault(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/vault/years`, {
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVaultYears(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingVault(false);
    }
  };

  const fetchVaultMonths = async (year: number) => {
    if (!selectedFirm) return;
    setIsLoadingVault(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/vault/${year}/months`, {
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVaultMonths(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingVault(false);
    }
  };

  const fetchVaultDays = async (year: number, month: number) => {
    if (!selectedFirm) return;
    setIsLoadingVault(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/vault/${year}/${month}/days`, {
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVaultDays(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingVault(false);
    }
  };

  const fetchVaultDayFiles = async (year: number, month: number, day: number, modFilter: string = '') => {
    if (!selectedFirm) return;
    setIsLoadingVault(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const filterQuery = modFilter ? `?module=${modFilter}` : '';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/vault/${year}/${month}/${day}${filterQuery}`, {
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setVaultFiles(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingVault(false);
    }
  };

  const handleDeleteVaultEntry = async (entryId: number) => {
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/vault/${entryId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        triggerToast("Document deleted successfully.");
        if (selectedVaultYear && selectedVaultMonth && selectedVaultDay) {
          fetchVaultDayFiles(selectedVaultYear, selectedVaultMonth, selectedVaultDay, vaultModuleFilter);
        }
      } else {
        triggerToast("Failed to delete document.");
      }
    } catch (err) {
      triggerToast("Connection failed during deletion.");
    }
  };

  const handleStubFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, targetModule: 'import_export' | 'eway_bills') => {
    if (!selectedFirm || !e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('module', targetModule);
    
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    setIsStubUploading(true);
    triggerToast(`Uploading document to ${targetModule === 'import_export' ? 'Import-Export' : 'E-Way Bills'}...`);
    
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/vault/upload-stub`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${activeToken}`
        },
        body: formData
      });
      
      if (res.ok) {
        triggerToast("Document uploaded and archived in Cloud Vault successfully!");
        fetchVaultYears();
      } else {
        triggerToast("Failed to upload document.");
      }
    } catch (err) {
      triggerToast("Upload failed due to connection error.");
    } finally {
      setIsStubUploading(false);
      if (e.target) e.target.value = '';
    }
  };

  // ─── TRADE DOCS (Import-Export) Handlers ───────────────────────────────────

  const fetchTradeDocs = async (options?: { manual?: boolean; silent?: boolean }) => {
    if (!selectedFirm) return;
    if (options?.manual) {
      setIsRefreshingTradeDocs(true);
    } else if (!options?.silent) {
      setIsLoadingTradeDocs(true);
    }
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/trade-docs`, {
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) setTradeDocs(await res.json());
    } catch (err) {
      console.error('fetchTradeDocs error:', err);
    } finally {
      setIsLoadingTradeDocs(false);
      setIsRefreshingTradeDocs(false);
      setIsInitialTradeDocsLoad(false);
    }
  };

  // Fetch on tab activation + poll while any record is still 'processing'
  useEffect(() => {
    if (activeTab !== 'import-export' || !selectedFirm) return;
    fetchTradeDocs();
    const interval = setInterval(() => {
      setTradeDocs((prev: any[]) => {
        if (prev.some((d: any) => d.status === 'processing')) fetchTradeDocs({ silent: true });
        return prev;
      });
    }, 3500);
    return () => clearInterval(interval);
  }, [activeTab, selectedFirm]);

  const handleTradeDocFilesSelected = async (fileList: FileList) => {
    if (!selectedFirm) return;
    const files = Array.from(fileList);
    if (!files.length) return;

    // Show progress entries immediately
    const progressEntries = files.map((f) => ({ id: `${f.name}-${Date.now()}`, name: f.name, progress: 0 }));
    setTradeDocUploadingFiles(progressEntries);
    setTradeDocSummaryMsg('');

    // Animate progress
    const animateProgress = (id: string, target: number) => {
      let p = 0;
      const step = setInterval(() => {
        p = Math.min(p + Math.random() * 18, target);
        setTradeDocUploadingFiles((prev: any[]) =>
          prev.map((f: any) => (f.id === id ? { ...f, progress: Math.round(p) } : f))
        );
        if (p >= target) clearInterval(step);
      }, 120);
    };
    progressEntries.forEach((e) => animateProgress(e.id, 80));

    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));

    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/trade-docs/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${activeToken}` },
        body: formData
      });
      const data = await res.json();

      // Complete all progress bars
      setTradeDocUploadingFiles((prev: any[]) =>
        prev.map((f: any) => ({ ...f, progress: 100 }))
      );

      const count = (data.uploaded || []).length;
      const errCount = (data.errors || []).length;
      let msg = `${count} file${count !== 1 ? 's' : ''} queued for extraction — AI processing…`;
      if (errCount > 0) msg += ` (${errCount} skipped)`;
      setTradeDocSummaryMsg(msg);
      setTimeout(() => setTradeDocUploadingFiles([]), 2500);

      if (data.uploaded?.length) {
        setTradeDocs((prev: any[]) => [...data.uploaded, ...prev]);
      }
    } catch (err) {
      setTradeDocSummaryMsg('Upload failed — connection error.');
      setTradeDocUploadingFiles([]);
    }
  };

  const handleTradeCellSave = async (docId: number, field: string) => {
    setEditingTradeCell(null);
    setSavingTradeDocId(docId);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/trade-docs/${docId}`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${activeToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_data: { [field]: editTradeValue } })
      });
      if (res.ok) {
        const updated = await res.json();
        setTradeDocs((prev: any[]) => prev.map((d: any) => (d.id === docId ? updated : d)));
      }
    } catch (err) {
      console.error('Trade cell save error:', err);
    } finally {
      setSavingTradeDocId(null);
    }
  };

  const handleVerifyTradeDoc = async (docId: number) => {
    setVerifyingTradeDocId(docId);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/trade-docs/${docId}/verify`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        const updated = await res.json();
        setTradeDocs((prev: any[]) => prev.map((d: any) => (d.id === docId ? updated : d)));
        triggerToast('Trade document verified successfully.');
      }
    } catch (err) {
      console.error('Verify trade doc error:', err);
    } finally {
      setVerifyingTradeDocId(null);
    }
  };

  const handleRetryTradeDoc = async (docId: number) => {
    setRetryingTradeDocId(docId);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/trade-docs/${docId}/retry-extraction`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        setTradeDocs((prev: any[]) =>
          prev.map((d: any) => (d.id === docId ? { ...d, status: 'processing', extraction_failed: false } : d))
        );
        triggerToast('Extraction re-queued.');
      }
    } catch (err) {
      console.error('Retry trade doc error:', err);
    } finally {
      setRetryingTradeDocId(null);
    }
  };

  const handleDeleteTradeDoc = async (docId: number) => {
    setIsDeletingTradeDoc(true);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/trade-docs/${docId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${activeToken}` }
      });
      if (res.ok) {
        setTradeDocs((prev: any[]) => prev.filter((d: any) => d.id !== docId));
        setDeletingTradeDocId(null);
        triggerToast('Trade document deleted.');
      }
    } catch (err) {
      console.error('Delete trade doc error:', err);
    } finally {
      setIsDeletingTradeDoc(false);
    }
  };

  // ─── END TRADE DOCS Handlers ───────────────────────────────────────────────

  // 4. File Drag & Drop Handlers

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFilesSelected(e.target.files);
    }
  };

  const handleFilesSelected = async (fileList: FileList) => {
    if (!selectedFirm) return;
    const filesToUpload = Array.from(fileList);
    
    // Validations
    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png'];
    const max_size = 10 * 1024 * 1024; // 10MB
    const validFiles: File[] = [];
    const localErrors: string[] = [];

    filesToUpload.forEach((f) => {
      const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase();
      if (!allowedExtensions.includes(ext)) {
        localErrors.push(`File "${f.name}" format not allowed. Use PDF, JPG, PNG.`);
        return;
      }
      if (f.size > max_size) {
        localErrors.push(`File "${f.name}" size exceeds 10MB.`);
        return;
      }
      validFiles.push(f);
    });

    if (localErrors.length > 0) {
      localErrors.forEach((errStr) => triggerToast(errStr));
    }

    if (validFiles.length === 0) return;

    // Append uploading placeholders
    const newUploadingItems = validFiles.map((f, idx) => ({
      id: `${Date.now()}_${idx}`,
      name: f.name,
      progress: 10,
      status: 'uploading'
    }));

    setUploadingFiles((prev) => [...prev, ...newUploadingItems]);

    // Simulate progress increments while uploading
    const progressInterval = setInterval(() => {
      setUploadingFiles((prev) => 
        prev.map((item) => 
          item.status === 'uploading' && item.progress < 90 
            ? { ...item, progress: item.progress + 15 } 
            : item
        )
      );
    }, 150);

    // Call API upload
    const formData = new FormData();
    validFiles.forEach((file) => {
      formData.append('files', file);
    });

    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    try {
      const res = await fetch(`${apiUrl}/api/firms/${selectedFirm.id}/invoices/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${activeToken}`
        },
        body: formData
      });

      const data = await res.json();
      
      clearInterval(progressInterval);

      if (res.ok) {
        setUploadingFiles((prev) => 
          prev.map((item) => {
            const wasUploaded = validFiles.some((f) => f.name === item.name);
            return wasUploaded ? { ...item, progress: 100, status: 'completed' } : item;
          })
        );

        setSummaryMessage(`${validFiles.length} file(s) uploaded. Extraction tasks enqueued.`);
        setTimeout(() => setSummaryMessage(''), 6000);

        fetchBills();
      } else {
        setUploadingFiles((prev) => 
          prev.map((item) => 
            item.status === 'uploading' ? { ...item, status: 'failed' } : item
          )
        );
        triggerToast(data.error || 'Invoice upload failed.');
      }
    } catch (err) {
      clearInterval(progressInterval);
      setUploadingFiles((prev) => 
        prev.map((item) => 
          item.status === 'uploading' ? { ...item, status: 'failed' } : item
        )
      );
      triggerToast('Network error during file uploads.');
    } finally {
      setTimeout(() => {
        setUploadingFiles((prev) => prev.filter((item) => item.status === 'uploading'));
      }, 2500);
    }
  };

  // 5. Save Inline Spreadsheet Cell Edits
  const handleCellSave = async (billId: number, field: string) => {
    setEditingCell(null);
    setSavingBillId(billId);
    
    // Read appropriate value
    let value: any = editValue;
    const numericFields = ['taxable_amount', 'cgst', 'sgst', 'igst', 'cess', 'total_amount'];
    if (numericFields.includes(field)) {
      value = parseFloat(editValue) || 0.0;
    } else if (field === 'party_gstin') {
      value = editValue.trim().toUpperCase() || null;
    } else if (field === 'invoice_date') {
      value = editValue.trim() || null;
    } else {
      value = editValue.trim() || null;
    }

    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${billId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          raw_data: {
            [field]: value
          }
        })
      });

      if (res.ok) {
        const updatedBill = await res.json();
        setBills((prev) => prev.map((b) => b.id === billId ? { ...b, ...updatedBill } : b));
        triggerToast(`Field "${field}" updated. Server validations re-run.`);
      } else {
        const errData = await res.json();
        triggerToast(errData.error || 'Failed to save cell edit.');
      }
    } catch (err) {
      triggerToast('Network connection failed.');
    } finally {
      setSavingBillId(null);
    }
  };

  // 6. Verify Invoice
  const handleVerifyBill = async (billId: number) => {
    setVerifyingBillId(billId);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${billId}/verify`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        setBills((prev) => prev.map((b) => b.id === billId ? { ...b, status: 'verified' } : b));
        triggerToast("Invoice successfully marked as verified.");
      } else {
        const data = await res.json();
        triggerToast(data.error || "Verification failed.");
      }
    } catch (err) {
      triggerToast("Failed to connect to verification server.");
    } finally {
      setVerifyingBillId(null);
    }
  };

  // 7. Retry Extraction
  const handleRetryExtraction = async (billId: number) => {
    setRetryingBillId(billId);
    const activeToken = token || localStorage.getItem('auth_token');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${billId}/retry-extraction`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${activeToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        setBills((prev) => prev.map((b) => b.id === billId ? { ...b, status: 'processing', validation_warnings: [], extraction_failed: false } : b));
        triggerToast("AI extraction retries enqueued.");
        fetchBills();
      } else {
        const data = await res.json();
        triggerToast(data.error || "Retry enqueuing failed.");
      }
    } catch (err) {
      triggerToast("Connection error during retry trigger.");
    } finally {
      setRetryingBillId(null);
    }
  };

  // Arithmetic Summaries logic based on includeUnverified toggle
  const getFilteredBills = () => {
    // Filter by type: Purchase or Sale
    const typedBills = bills.filter((b) => {
      const type = b.raw_data?.bill_type || 'purchase';
      return type === invoiceType;
    });

    if (includeUnverified) {
      // Exclude only active processing
      return typedBills.filter((b) => b.status !== 'processing');
    }
    // Only verified rows
    return typedBills.filter((b) => b.status === 'verified');
  };

  const filteredBillsForStats = getFilteredBills();
  const summaryTaxable = filteredBillsForStats.reduce((sum, b) => sum + (b.raw_data?.taxable_amount || 0.0), 0.0);
  const summaryIGST = filteredBillsForStats.reduce((sum, b) => sum + (b.raw_data?.igst || 0.0), 0.0);
  const summaryCGST = filteredBillsForStats.reduce((sum, b) => sum + (b.raw_data?.cgst || 0.0), 0.0);
  const summarySGST = filteredBillsForStats.reduce((sum, b) => sum + (b.raw_data?.sgst || 0.0), 0.0);
  const summaryTotal = filteredBillsForStats.reduce((sum, b) => sum + (b.raw_data?.total_amount || 0.0), 0.0);

  // Format Bytes Utility
  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  // Auth session restore loading
  if (!mounted || authLoading) {
    return (
      <div className="flex min-h-screen bg-bg-primary text-text-primary font-sans items-center justify-center transition-colors duration-200">
        <div className="flex flex-col items-center gap-4 text-text-secondary font-mono text-xs">
          <Loader2 className="w-8 h-8 animate-spin text-text-primary" />
          <p>Loading workspace…</p>
        </div>
      </div>
    );
  }

  // ZERO FIRMS FULL SCREEN STATE
  if (firms.length === 0) {
    return (
      <div className="flex flex-col min-h-screen bg-bg-primary text-text-primary font-sans transition-colors duration-200 selection:bg-text-primary selection:text-bg-primary">
        <header className="w-full flex justify-between items-center px-4 md:px-8 py-6 max-w-7xl mx-auto">
          <div className="text-lg font-bold tracking-tight">LedgerPro</div>
          <button
            onClick={toggleTheme}
            className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
            aria-label="Toggle Theme"
          >
            {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </button>
        </header>

        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md border border-border-subtle rounded-lg bg-bg-secondary p-8 shadow-2xl text-center space-y-6 animate-in fade-in zoom-in-95 duration-200">
          <div className="w-16 h-16 border border-border-subtle bg-bg-primary rounded-full flex items-center justify-center mx-auto text-text-primary">
            <Building className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight">Connect your first firm</h2>
            <p className="text-sm text-text-secondary max-w-xs mx-auto leading-relaxed">
              Welcome to LedgerPro v2. Add your first corporate client or bookkeeping ledger to access automation workspaces.
            </p>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="w-full py-3 bg-accent text-accent-foreground font-semibold rounded hover:opacity-90 transition-all flex items-center justify-center gap-2 active:scale-98"
          >
            <Plus className="w-4 h-4" /> Add Client Firm
          </button>
          </div>
        </div>

        <AddFirmModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
        <SaasFooter variant="minimal" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-bg-primary text-text-primary font-sans transition-colors duration-200 selection:bg-text-primary selection:text-bg-primary relative">
      
      {/* Toast Notifications Box */}
      <div className="fixed top-6 right-6 z-50 flex flex-col gap-3 pointer-events-none max-w-sm w-full px-4 md:px-0">
        {toasts.map((toast) => (
          <div 
            key={toast.id}
            className="p-4 bg-bg-secondary text-text-primary border border-border-subtle rounded-md shadow-2xl text-xs font-mono flex items-start gap-2.5 pointer-events-auto animate-in slide-in-from-right duration-200"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div className="flex-1">{toast.message}</div>
            <button 
              onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              className="hover:opacity-70 transition-opacity pointer-events-auto"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>

      {/* Sidebar Navigation — desktop */}
      <aside className="w-64 border-r border-border-subtle bg-bg-secondary flex flex-col justify-between hidden md:flex shrink-0">
        <div className="p-6 space-y-8">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold tracking-tight">LedgerPro</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 border border-border-subtle rounded bg-bg-primary">
              v2.0
            </span>
          </div>

          <DashboardNav activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        <div className="p-6 border-t border-border-subtle text-xs font-mono text-text-secondary">
          <div>Workspace Connected</div>
          <div className="flex items-center gap-1.5 mt-1 text-green-500 font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            Operational
          </div>
        </div>
      </aside>

      {/* Mobile drawer overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute left-0 top-0 bottom-0 w-72 max-w-[85vw] bg-bg-secondary border-r border-border-subtle flex flex-col justify-between animate-in slide-in-from-left duration-200 shadow-2xl">
            <div className="p-6 space-y-8">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold tracking-tight">LedgerPro</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 border border-border-subtle rounded bg-bg-primary">
                    v2.0
                  </span>
                </div>
                <button
                  onClick={() => setMobileNavOpen(false)}
                  className="p-2 border border-border-subtle rounded hover:bg-bg-primary transition-colors"
                  aria-label="Close navigation"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <DashboardNav
                activeTab={activeTab}
                onTabChange={setActiveTab}
                onNavigate={() => setMobileNavOpen(false)}
                layout="drawer"
              />
            </div>
            <div className="p-6 border-t border-border-subtle text-xs font-mono text-text-secondary">
              <div>Workspace Connected</div>
              <div className="flex items-center gap-1.5 mt-1 text-green-500 font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                Operational
              </div>
            </div>
          </aside>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-h-screen min-w-0">
        
        {/* Top Header */}
        <header className="h-16 border-b border-border-subtle bg-bg-primary flex items-center justify-between px-4 md:px-8 transition-colors duration-200 shrink-0">
          <div className="flex items-center gap-3 md:gap-6 min-w-0">
            <button
              onClick={() => setMobileNavOpen(true)}
              className="md:hidden p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors shrink-0"
              aria-label="Open navigation"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="md:hidden flex items-center gap-2 shrink-0">
              <span className="text-lg font-bold tracking-tight">LedgerPro</span>
            </div>

            {/* Firm Switcher Dropdown */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-text-secondary hidden sm:inline">Workspace:</span>
              <select
                value={selectedFirm?.id || ''}
                onChange={(e) => {
                  const id = parseInt(e.target.value);
                  const selected = firms.find((f) => f.id === id);
                  if (selected && selected.status === 'active') {
                    setSelectedFirm(selected);
                  }
                }}
                className="bg-bg-secondary border border-border-subtle rounded px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent font-medium font-mono cursor-pointer"
              >
                <option value="" disabled>Select Firm</option>
                {firms.map((firm) => (
                  <option 
                    key={firm.id} 
                    value={firm.id} 
                    disabled={firm.status !== 'active'}
                  >
                    {firm.name} {firm.status !== 'active' ? ' (Verification Pending)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setIsModalOpen(true)}
              className="px-2.5 py-1.5 border border-border-subtle rounded text-xs hover:bg-bg-secondary transition-all font-mono flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Add Client</span>
            </button>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className="p-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              aria-label="Toggle Theme"
            >
              {theme === 'light' ? <Moon className="w-4.5 h-4.5" /> : <Sun className="w-4.5 h-4.5" />}
            </button>

            {/* User Dropdown */}
            <div className="relative">
              <button
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                className="flex items-center gap-2 p-1.5 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt={user.name} className="w-5 h-5 rounded-full border border-border-subtle" />
                ) : (
                  <div className="w-5 h-5 rounded-full bg-accent text-accent-foreground text-[10px] font-bold flex items-center justify-center">
                    {user?.name?.charAt(0).toUpperCase() || 'A'}
                  </div>
                )}
                <span className="text-xs font-semibold font-mono hidden sm:inline">{user?.name}</span>
                <ChevronDown className="w-3.5 h-3.5 text-text-secondary" />
              </button>

              {userDropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 border border-border-subtle rounded-md bg-bg-secondary p-2 shadow-xl z-50 animate-in fade-in slide-in-from-top-2 duration-100">
                  <div className="px-3 py-2 border-b border-border-subtle text-xs space-y-0.5">
                    <div className="font-bold text-text-primary">{user?.name}</div>
                    <div className="text-text-secondary font-mono truncate">{user?.email}</div>
                  </div>
                  <button
                    onClick={logout}
                    className="w-full text-left px-3 py-2 text-xs font-semibold hover:bg-bg-primary rounded text-red-500 flex items-center gap-2 mt-1"
                  >
                    <LogOut className="w-3.5 h-3.5" /> Log Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Viewports */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8 max-w-5xl w-full mx-auto space-y-8 animate-in fade-in duration-300">
          
          {/* TAB 1: OVERVIEW / ANALYTICS */}
          {activeTab === 'overview' && (
            <div className="space-y-8">
              {/* Header row */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-extrabold tracking-tight">Overview</h1>
                  <p className="text-sm text-text-secondary mt-1">
                    Verified invoice analytics for <span className="font-semibold text-text-primary">{selectedFirm?.name || 'your firm'}</span>. Only confirmed bills are counted.
                  </p>
                </div>

                {selectedFirm && (
                  <div className="flex items-center gap-2">
                    {/* Range Selector */}
                    <div className="flex border border-border-subtle rounded overflow-hidden font-mono text-xs">
                      {(['month', 'quarter', 'year'] as const).map((r) => (
                        <button
                          key={r}
                          onClick={() => setAnalyticsRange(r)}
                          className={`px-3 py-1.5 capitalize transition-colors ${
                            analyticsRange === r
                              ? 'bg-accent text-accent-foreground font-bold'
                              : 'bg-bg-secondary hover:bg-bg-primary text-text-secondary'
                          }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={() => fetchAnalytics(analyticsRange)}
                      className="p-1.5 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
                      title="Refresh analytics"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isLoadingAnalytics ? 'animate-spin' : ''}`} />
                    </button>
                  </div>
                )}
              </div>

              {!selectedFirm ? (
                <div className="flex flex-col items-center justify-center p-12 md:p-20 border border-dashed border-border-subtle rounded-lg bg-bg-secondary/10 text-center space-y-4">
                  <Building className="w-12 h-12 text-text-secondary opacity-50" />
                  <p className="font-mono text-sm text-text-secondary">No firm selected. Choose a client workspace from the header selector.</p>
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all flex items-center gap-2"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Client Firm
                  </button>
                </div>
              ) : isLoadingAnalytics && !analyticsSummary ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4 text-text-secondary font-mono text-xs">
                  <Loader2 className="w-8 h-8 animate-spin text-text-primary" />
                  <p>Loading analytics…</p>
                </div>
              ) : (
                <>
                  {/* ── STAT CARDS ── */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">

                    {/* Total Sales Card — click drills into Sales invoices */}
                    <button
                      onClick={() => {
                        setBillTypeFilter('sale');
                        if (analyticsSummary?.period_start) setStartDate(analyticsSummary.period_start);
                        if (analyticsSummary?.period_end) setEndDate(analyticsSummary.period_end);
                        setActiveTab('invoices');
                      }}
                      className="text-left border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-3 hover:border-text-primary/40 hover:shadow-md transition-all active:scale-[0.98] cursor-pointer group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-bold">Total Sales</span>
                        <TrendingUp className="w-4 h-4 text-text-secondary group-hover:text-text-primary transition-colors" />
                      </div>
                      <div className="text-2xl font-extrabold tracking-tight">
                        ₹{((analyticsSummary?.total_sales_turnover || 0) / 100000).toFixed(2)}L
                      </div>
                      <div className="text-[10px] font-mono text-text-secondary">
                        Taxable turnover · {analyticsSummary?.range || analyticsRange} · verified only
                      </div>
                    </button>

                    {/* Total Purchases Card — click drills into Purchase invoices */}
                    <button
                      onClick={() => {
                        setBillTypeFilter('purchase');
                        if (analyticsSummary?.period_start) setStartDate(analyticsSummary.period_start);
                        if (analyticsSummary?.period_end) setEndDate(analyticsSummary.period_end);
                        setActiveTab('invoices');
                      }}
                      className="text-left border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-3 hover:border-text-primary/40 hover:shadow-md transition-all active:scale-[0.98] cursor-pointer group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-bold">Total Purchases</span>
                        <TrendingDown className="w-4 h-4 text-text-secondary group-hover:text-text-primary transition-colors" />
                      </div>
                      <div className="text-2xl font-extrabold tracking-tight">
                        ₹{((analyticsSummary?.total_purchase_turnover || 0) / 100000).toFixed(2)}L
                      </div>
                      <div className="text-[10px] font-mono text-text-secondary">
                        Taxable turnover · {analyticsSummary?.range || analyticsRange} · verified only
                      </div>
                    </button>

                    {/* Net GST Liability Card */}
                    <div className={`border rounded-lg p-5 space-y-3 ${
                      (analyticsSummary?.net_gst_liability || 0) >= 0
                        ? 'border-border-subtle bg-bg-secondary'
                        : 'border-border-subtle bg-bg-secondary'
                    }`}>
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-bold">Net GST Liability</span>
                        <BarChart2 className="w-4 h-4 text-text-secondary" />
                      </div>
                      <div className={`text-2xl font-extrabold tracking-tight ${
                        (analyticsSummary?.net_gst_liability || 0) >= 0 ? 'text-text-primary' : 'text-text-primary'
                      }`}>
                        {(analyticsSummary?.net_gst_liability || 0) < 0 ? '-' : ''}
                        ₹{(Math.abs(analyticsSummary?.net_gst_liability || 0) / 100000).toFixed(2)}L
                      </div>
                      <div className="text-[10px] font-mono text-text-secondary">
                        {(analyticsSummary?.net_gst_liability || 0) >= 0 ? 'Output tax payable to govt' : 'ITC surplus (credit available)'}
                      </div>
                      {/* GST breakdown sub-line */}
                      <div className="grid grid-cols-2 gap-x-3 text-[9px] font-mono text-text-secondary pt-1 border-t border-border-subtle">
                        <span>Output: ₹{((analyticsSummary?.output_tax || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                        <span>ITC: ₹{((analyticsSummary?.input_tax_credit || 0)).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                      </div>
                    </div>
                  </div>

                  {/* ── QUICK LEDGER COUNTERS ── */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                    {[
                      { label: 'Total Bills', value: bills.length },
                      { label: 'Needs Review', value: bills.filter(b => b.status === 'needs_review').length },
                      { label: 'Verified', value: bills.filter(b => b.status === 'verified').length },
                      { label: 'Processing', value: bills.filter(b => b.status === 'processing').length },
                    ].map((s) => (
                      <div key={s.label} className="border border-border-subtle rounded-lg p-3 bg-bg-secondary flex flex-col gap-1">
                        <span className="text-[9px] uppercase tracking-wider text-text-secondary font-bold">{s.label}</span>
                        <span className="text-lg font-extrabold">{s.value}</span>
                      </div>
                    ))}
                  </div>

                  {/* ── CHARTS ROW ── */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                    {/* Line Chart — spans 2/3 of grid */}
                    <div className="lg:col-span-2 border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold tracking-tight">Turnover Over Time</h3>
                        <span className="text-[10px] font-mono text-text-secondary uppercase">Purchase vs Sale · {analyticsRange}</span>
                      </div>
                      {analyticsTurnover.length === 0 ? (
                        <div className="h-56 flex flex-col items-center justify-center gap-3 text-text-secondary font-mono text-xs">
                          <BarChart2 className="w-8 h-8 opacity-40" />
                          <p>No verified invoices for this period.</p>
                          <p className="text-[10px]">Verify bills in the Invoices tab to populate charts.</p>
                          <button
                            onClick={() => setActiveTab('invoices')}
                            className="mt-1 px-3 py-1.5 bg-accent text-accent-foreground text-[10px] font-semibold rounded hover:opacity-90 transition-all"
                          >
                            Go to Invoices
                          </button>
                        </div>
                      ) : (
                        <ResponsiveContainer width="100%" height={220}>
                          <LineChart data={analyticsTurnover} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle, #e5e7eb)" strokeOpacity={0.5} />
                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 10, fill: 'var(--color-text-secondary, #6b7280)', fontFamily: 'monospace' }}
                              tickLine={false}
                              axisLine={false}
                            />
                            <YAxis
                              tick={{ fontSize: 10, fill: 'var(--color-text-secondary, #6b7280)', fontFamily: 'monospace' }}
                              tickLine={false}
                              axisLine={false}
                              tickFormatter={(v) => v >= 100000 ? `${(v/100000).toFixed(1)}L` : v >= 1000 ? `${(v/1000).toFixed(0)}K` : String(v)}
                            />
                            <Tooltip
                              contentStyle={{
                                background: 'var(--color-bg-secondary, #f9fafb)',
                                border: '1px solid var(--color-border-subtle, #e5e7eb)',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontFamily: 'monospace'
                              }}
                              formatter={(value: any) => [`₹${Number(value).toLocaleString('en-IN')}`, undefined]}
                            />
                            <Legend
                              wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace', textTransform: 'capitalize' }}
                            />
                            <Line
                              type="monotone"
                              dataKey="purchase"
                              name="Purchase"
                              stroke="var(--color-text-primary, #111827)"
                              strokeWidth={2}
                              dot={{ r: 3, fill: 'var(--color-text-primary, #111827)' }}
                              activeDot={{ r: 5 }}
                            />
                            <Line
                              type="monotone"
                              dataKey="sale"
                              name="Sale"
                              stroke="var(--color-text-secondary, #6b7280)"
                              strokeWidth={2}
                              strokeDasharray="5 3"
                              dot={{ r: 3, fill: 'var(--color-text-secondary, #6b7280)' }}
                              activeDot={{ r: 5 }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )}
                    </div>

                    {/* Pie Chart — 1/3 of grid */}
                    <div className="border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-4">
                      <div>
                        <h3 className="text-sm font-bold tracking-tight">Purchase vs Sale Split</h3>
                        <p className="text-[10px] font-mono text-text-secondary">By taxable amount</p>
                      </div>
                      {(!analyticsSummary || (analyticsSummary.total_purchase_turnover === 0 && analyticsSummary.total_sales_turnover === 0)) ? (
                        <div className="h-48 flex flex-col items-center justify-center gap-3 text-text-secondary font-mono text-xs">
                          <BarChart2 className="w-8 h-8 opacity-40" />
                          <p>No data yet.</p>
                          <button
                            onClick={() => setActiveTab('invoices')}
                            className="mt-1 px-3 py-1.5 bg-accent text-accent-foreground text-[10px] font-semibold rounded hover:opacity-90 transition-all"
                          >
                            Upload Invoices
                          </button>
                        </div>
                      ) : (
                        <>
                          <ResponsiveContainer width="100%" height={170}>
                            <PieChart>
                              <Pie
                                data={analyticsSummary?.purchase_vs_sale || []}
                                cx="50%"
                                cy="50%"
                                innerRadius={42}
                                outerRadius={68}
                                dataKey="value"
                                paddingAngle={3}
                                onClick={(entry: any) => {
                                  const type = entry.name === 'Sales' ? 'sale' : 'purchase';
                                  setBillTypeFilter(type);
                                  if (analyticsSummary?.period_start) setStartDate(analyticsSummary.period_start);
                                  if (analyticsSummary?.period_end) setEndDate(analyticsSummary.period_end);
                                  setActiveTab('invoices');
                                }}
                              >
                                {(analyticsSummary?.purchase_vs_sale || []).map((_: any, i: number) => (
                                  <Cell
                                    key={`cell-${i}`}
                                    fill={i === 0 ? 'var(--color-text-primary, #111827)' : 'var(--color-text-secondary, #9ca3af)'}
                                    cursor="pointer"
                                  />
                                ))}
                              </Pie>
                              <Tooltip
                                contentStyle={{
                                  background: 'var(--color-bg-secondary, #f9fafb)',
                                  border: '1px solid var(--color-border-subtle, #e5e7eb)',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontFamily: 'monospace'
                                }}
                                formatter={(value: any) => [`₹${Number(value).toLocaleString('en-IN')}`, undefined]}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                          {/* Legend */}
                          <div className="space-y-2 font-mono text-xs">
                            {(analyticsSummary?.purchase_vs_sale || []).map((item: any, i: number) => (
                              <div key={item.name} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className={`w-2.5 h-2.5 rounded-full ${i === 0 ? 'bg-text-primary' : 'bg-text-secondary'}`} />
                                  <span className="text-text-secondary">{item.name}</span>
                                </div>
                                <span className="font-bold">₹{Number(item.value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* ── FIRM IDENTITY CARD ── */}
                  <div className="border border-border-subtle rounded-lg bg-bg-secondary p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="space-y-1">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary border border-border-subtle px-2 py-0.5 rounded bg-bg-primary">Connected Client</span>
                        <h3 className="text-lg font-bold pt-2 flex items-center gap-2">
                          <Building className="w-4 h-4" /> {selectedFirm?.name}
                        </h3>
                      </div>
                      <span className="inline-flex items-center gap-1.5 text-xs font-mono text-green-500 font-bold bg-green-500/10 px-2.5 py-0.5 rounded-full border border-green-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                        Active
                      </span>
                    </div>
                    <div className="grid sm:grid-cols-4 gap-4 border-t border-border-subtle pt-4 text-xs font-mono">
                      <div><span className="text-text-secondary block">GSTIN</span><span className="font-semibold">{selectedFirm?.gstin || '—'}</span></div>
                      <div><span className="text-text-secondary block">Owner</span><span className="font-semibold">{selectedFirm?.owner_email}</span></div>
                      <div><span className="text-text-secondary block">Location</span><span className="font-semibold">{selectedFirm?.city}, {selectedFirm?.state}</span></div>
                      <div><span className="text-text-secondary block">Registered</span><span className="font-semibold">{selectedFirm ? new Date(selectedFirm.created_at).toLocaleDateString() : '—'}</span></div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 2: INVOICES (WITH EDITABLE REVIEW GRID & VERIFY ACTIONS) */}
          {activeTab === 'invoices' && (
            <div className="space-y-6">
              
              {/* Header section */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-extrabold tracking-tight">Invoices</h1>
                  <p className="text-sm text-text-secondary mt-1">Spreadsheet-style inline editing for tax audits and ERP synchronization.</p>
                </div>

                <div className="flex border border-border-subtle rounded overflow-hidden font-mono text-xs">
                  <button 
                    onClick={() => setInvoiceType('purchase')}
                    className={`px-3 py-1.5 ${invoiceType === 'purchase' ? 'bg-accent text-accent-foreground font-bold' : 'bg-bg-secondary hover:bg-bg-primary'}`}
                  >
                    Purchase Bills
                  </button>
                  <button 
                    onClick={() => setInvoiceType('sales')}
                    className={`px-3 py-1.5 ${invoiceType === 'sales' ? 'bg-accent text-accent-foreground font-bold' : 'bg-bg-secondary hover:bg-bg-primary'}`}
                  >
                    Sales Invoices
                  </button>
                </div>
              </div>

              {selectedFirm ? (
                <div className="space-y-8">
                  
                  {/* Search and Filters Bar */}
                  <div className="flex flex-wrap gap-4 items-center bg-bg-secondary p-4 border border-border-subtle rounded-md text-xs font-mono">
                    <div className="flex-1 min-w-[200px]">
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Search Invoice / Party</label>
                      <input 
                        type="text"
                        placeholder="Search..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Status</label>
                      <select 
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary cursor-pointer"
                      >
                        <option value="">All Statuses</option>
                        <option value="processing">Processing</option>
                        <option value="needs_review">Needs Review</option>
                        <option value="verified">Verified</option>
                        <option value="extraction_failed">Failed</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Bill Type</label>
                      <select 
                        value={billTypeFilter}
                        onChange={(e) => setBillTypeFilter(e.target.value)}
                        className="bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary cursor-pointer"
                      >
                        <option value="">All Types</option>
                        <option value="purchase">Purchase</option>
                        <option value="sale">Sale</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Start Date</label>
                      <input 
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">End Date</label>
                      <input 
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary"
                      />
                    </div>

                    <div className="self-end">
                      <button 
                        onClick={() => {
                          setSearchQuery('');
                          setStatusFilter('');
                          setBillTypeFilter('');
                          setStartDate('');
                          setEndDate('');
                        }}
                        className="px-3 py-1.5 border border-border-subtle rounded hover:bg-bg-primary transition-colors text-text-secondary hover:text-text-primary font-bold"
                      >
                        Clear Filters
                      </button>
                    </div>
                  </div>

                  {/* Upload Drop Zone Panel */}
                  <div 
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border border-dashed rounded-lg p-10 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-4 ${
                      isDragging 
                        ? 'border-accent bg-bg-secondary/50 scale-[1.01]' 
                        : 'border-border-subtle bg-bg-secondary/20 hover:border-text-primary/30'
                    }`}
                  >
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      multiple 
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={handleFileChange}
                      className="hidden" 
                    />
                    
                    <div className="w-12 h-12 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                      <Upload className="w-5 h-5" />
                    </div>

                    <div className="space-y-1">
                      <p className="font-mono text-sm font-semibold">Drag & drop files or click to browse</p>
                      <p className="text-xs text-text-secondary">Supports PDF, JPG, PNG up to 10MB per file</p>
                    </div>
                  </div>

                  {/* Summary progress bar */}
                  {(uploadingFiles.length > 0 || summaryMessage) && (
                    <div className="border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-4">
                      {summaryMessage && (
                        <div className="text-xs font-mono text-text-primary font-bold flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-green-500" /> {summaryMessage}
                        </div>
                      )}
                      
                      {uploadingFiles.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-xs font-mono text-text-secondary uppercase tracking-wider font-bold">Uploading files...</h4>
                          <div className="space-y-2">
                            {uploadingFiles.map((file) => (
                              <div key={file.id} className="text-xs font-mono space-y-1">
                                <div className="flex justify-between text-text-secondary">
                                  <span className="truncate max-w-xs">{file.name}</span>
                                  <span>{file.progress}%</span>
                                </div>
                                <div className="w-full bg-bg-primary h-1.5 rounded overflow-hidden">
                                  <div 
                                    className="bg-accent h-1.5 transition-all duration-150" 
                                    style={{ width: `${file.progress}%` }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Calculation summaries widget */}
                  <div className="border border-border-subtle rounded-lg bg-bg-secondary p-6 space-y-6">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-bold">Workspace Ledger Summaries</h3>
                        <p className="text-xs text-text-secondary font-mono mt-0.5">Summary is calculated from target bills.</p>
                      </div>

                      {/* Include Unverified Toggle */}
                      <label className="flex items-center gap-2 text-xs font-mono text-text-primary cursor-pointer select-none">
                        <input 
                          type="checkbox" 
                          checked={includeUnverified}
                          onChange={(e) => setIncludeUnverified(e.target.checked)}
                          className="w-4 h-4 accent-black dark:accent-white cursor-pointer"
                        />
                        Include unverified entries
                      </label>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm font-mono pt-4 border-t border-border-subtle">
                      <div className="space-y-1">
                        <span className="text-xs text-text-secondary block">Taxable value</span>
                        <span className="font-bold text-base">₹{summaryTaxable.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-xs text-text-secondary block">CGST amount</span>
                        <span className="font-bold text-base">₹{summaryCGST.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-xs text-text-secondary block">SGST amount</span>
                        <span className="font-bold text-base">₹{summarySGST.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-xs text-text-secondary block">IGST amount</span>
                        <span className="font-bold text-base">₹{summaryIGST.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                      </div>
                      <div className="space-y-1 border-t sm:border-t-0 sm:border-l border-border-subtle pt-3 sm:pt-0 sm:pl-4">
                        <span className="text-xs text-text-secondary block">Total amount</span>
                        <span className="font-bold text-base text-text-primary">₹{summaryTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                      </div>
                    </div>
                  </div>

                  {/* Spreadsheet Grid Table */}
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-bold tracking-tight">Audit Verification Grid</h3>
                      <button
                        onClick={handleGenerateExcel}
                        disabled={bills.length === 0}
                        className="px-3 py-1.5 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 active:scale-95 transition-all flex items-center gap-1.5 disabled:opacity-50 font-mono"
                      >
                        <FileText className="w-4 h-4" /> Generate Excel
                      </button>
                    </div>
                    
                    {isInitialBillsLoad && isLoadingBills ? (
                      <div className="border border-dashed border-border-subtle rounded-lg p-12 flex flex-col items-center justify-center gap-3 text-text-secondary font-mono text-xs bg-bg-secondary/5">
                        <Loader2 className="w-8 h-8 animate-spin text-text-primary" />
                        <p>Loading invoices…</p>
                      </div>
                    ) : bills.length === 0 ? (
                      <div className="border border-dashed border-border-subtle rounded-lg p-12 text-center text-xs text-text-secondary font-mono bg-bg-secondary/5 flex flex-col items-center gap-4">
                        <Upload className="w-10 h-10 opacity-40" />
                        <p>No client invoices uploaded.</p>
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all flex items-center gap-2"
                        >
                          <Upload className="w-3.5 h-3.5" /> Upload Invoices
                        </button>
                      </div>
                    ) : (
                      <div className="border border-border-subtle rounded-lg bg-bg-secondary overflow-x-auto shadow-sm">
                        <table className="w-full text-left border-collapse text-xs font-mono min-w-[1000px]">
                          <thead>
                            <tr className="bg-bg-primary text-text-secondary border-b border-border-subtle text-[10px] uppercase font-bold tracking-wider">
                              <th className="p-3 border-r border-border-subtle min-w-[100px]">Date of Bill</th>
                              <th className="p-3 border-r border-border-subtle min-w-[110px]">Invoice No</th>
                              <th className="p-3 border-r border-border-subtle min-w-[160px]">From (Party)</th>
                              <th className="p-3 border-r border-border-subtle min-w-[125px]">Party GSTIN</th>
                              <th className="p-3 border-r border-border-subtle text-right min-w-[105px]">Taxable Amt</th>
                              <th className="p-3 border-r border-border-subtle text-right min-w-[85px]">CGST</th>
                              <th className="p-3 border-r border-border-subtle text-right min-w-[85px]">SGST</th>
                              <th className="p-3 border-r border-border-subtle text-right min-w-[85px]">IGST</th>
                              <th className="p-3 border-r border-border-subtle text-right min-w-[105px]">Total Amt</th>
                              <th className="p-3 border-r border-border-subtle text-center min-w-[80px]">Type</th>
                              <th className="p-3 border-r border-border-subtle min-w-[130px]">Status</th>
                              <th className="p-3 text-center min-w-[110px]">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border-subtle">
                            {bills.map((bill) => {
                              const rData = bill.raw_data || {};
                              const isFailed = bill.status === 'extraction_failed';
                              const isProcessing = bill.status === 'processing';
                              
                              return (
                                <tr 
                                  key={bill.id}
                                  className={`hover:bg-bg-primary/20 transition-colors ${
                                    savingBillId === bill.id ? 'opacity-60' : ''
                                  } ${
                                    isFailed 
                                      ? 'bg-red-500/5 hover:bg-red-500/10 border-l-2 border-l-red-500' 
                                      : bill.validation_warnings?.length > 0 
                                      ? 'bg-yellow-500/5 hover:bg-yellow-500/10' 
                                      : ''
                                  }`}
                                >
                                  {/* Render Cells */}
                                  {[
                                    { field: 'invoice_date', val: rData.invoice_date || '', align: 'left' },
                                    { field: 'invoice_number', val: rData.invoice_number || '', align: 'left' },
                                    { field: 'party_name', val: rData.party_name || '', align: 'left' },
                                    { field: 'party_gstin', val: rData.party_gstin || '', align: 'left' },
                                    { field: 'taxable_amount', val: rData.taxable_amount !== undefined ? rData.taxable_amount : '', align: 'right' },
                                    { field: 'cgst', val: rData.cgst !== undefined ? rData.cgst : '', align: 'right' },
                                    { field: 'sgst', val: rData.sgst !== undefined ? rData.sgst : '', align: 'right' },
                                    { field: 'igst', val: rData.igst !== undefined ? rData.igst : '', align: 'right' },
                                    { field: 'total_amount', val: rData.total_amount !== undefined ? rData.total_amount : '', align: 'right' },
                                  ].map((cell) => {
                                    const isEditing = editingCell?.billId === bill.id && editingCell?.field === cell.field;
                                    return (
                                      <td 
                                        key={cell.field}
                                        onClick={() => {
                                          if (!isProcessing && bill.status !== 'verified') {
                                            setEditingCell({ billId: bill.id, field: cell.field });
                                            setEditValue(cell.val.toString());
                                          }
                                        }}
                                        className={`p-2 border-r border-border-subtle cursor-pointer relative group ${
                                          cell.align === 'right' ? 'text-right' : 'text-left'
                                        }`}
                                      >
                                        {isEditing ? (
                                          <input
                                            type="text"
                                            value={editValue}
                                            autoFocus
                                            onChange={(e) => setEditValue(e.target.value)}
                                            onBlur={() => handleCellSave(bill.id, cell.field)}
                                            onKeyDown={(e) => {
                                              if (e.key === 'Enter') handleCellSave(bill.id, cell.field);
                                              if (e.key === 'Escape') setEditingCell(null);
                                            }}
                                            className="w-full px-1 py-0.5 bg-bg-primary border border-accent rounded focus:outline-none text-xs font-mono text-text-primary"
                                          />
                                        ) : (
                                          <div className="flex items-center justify-between gap-1">
                                            <span className="truncate">{cell.val}</span>
                                            {(!isProcessing && bill.status !== 'verified') && (
                                              <Edit2 className="w-2.5 h-2.5 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity" />
                                            )}
                                          </div>
                                        )}
                                      </td>
                                    );
                                  })}

                                  {/* Bill Type Cell */}
                                  <td className="p-2 border-r border-border-subtle text-center">
                                    {bill.status === 'verified' ? (
                                      <span className="capitalize">{rData.bill_type || 'purchase'}</span>
                                    ) : (
                                      <select
                                        value={rData.bill_type || 'purchase'}
                                        disabled={isProcessing}
                                        onChange={(e) => {
                                          setEditValue(e.target.value);
                                          handleCellSave(bill.id, 'bill_type');
                                        }}
                                        className="bg-bg-primary border border-border-subtle rounded px-1.5 py-0.5 text-[10px] font-mono focus:outline-none text-text-primary cursor-pointer"
                                      >
                                        <option value="purchase">Purchase</option>
                                        <option value="sale">Sale</option>
                                      </select>
                                    )}
                                  </td>

                                  {/* Status Cell with Hover Warning Tooltip */}
                                  <td className="p-2 border-r border-border-subtle">
                                    <div className="flex items-center gap-1.5">
                                      {isProcessing && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.25 rounded bg-bg-primary border border-border-subtle text-text-secondary">
                                          <Loader2 className="w-2.5 h-2.5 animate-spin" /> Process
                                        </span>
                                      )}
                                      {bill.status === 'needs_review' && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.25 rounded bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 font-bold">
                                          <Clock className="w-2.5 h-2.5" /> Review
                                        </span>
                                      )}
                                      {bill.status === 'verified' && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.25 rounded bg-green-500/10 border border-green-500/20 text-green-500 font-bold">
                                          <CheckCircle2 className="w-2.5 h-2.5" /> Verified
                                        </span>
                                      )}
                                      {isFailed && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.25 rounded bg-red-500/10 border border-red-500/20 text-red-500 font-bold">
                                          <AlertCircle className="w-2.5 h-2.5" /> Failed
                                        </span>
                                      )}

                                      {/* Validation warnings tooltip icon */}
                                      {(!isProcessing && bill.validation_warnings?.length > 0) && (
                                        <div className="relative group inline-block cursor-help">
                                          <span className="text-yellow-500 font-bold hover:opacity-80">&#9888;</span>
                                          <div className="absolute left-0 bottom-full mb-1.5 hidden group-hover:block z-50 bg-bg-secondary text-text-primary p-2.5 rounded text-[10px] w-64 border border-border-subtle shadow-xl font-mono leading-relaxed pointer-events-none">
                                            <div className="font-bold border-b border-border-subtle pb-1 mb-1 flex items-center gap-1">
                                              <Info className="w-3 h-3 text-yellow-500" /> Warnings list:
                                            </div>
                                            {bill.validation_warnings.map((w: string, idx: number) => (
                                              <div key={idx} className="mb-0.5">&bull; {w}</div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </td>

                                  {/* Actions Cell */}
                                  <td className="p-2 text-center flex items-center justify-center gap-2">
                                    <button 
                                      onClick={() => setViewingBill(bill)}
                                      className="px-2 py-1 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all active:scale-95"
                                    >
                                      View
                                    </button>
                                    
                                    {bill.status === 'needs_review' && (
                                      <>
                                        <button 
                                          onClick={() => handleVerifyBill(bill.id)}
                                          disabled={verifyingBillId === bill.id}
                                          className="px-2 py-1 bg-accent text-accent-foreground rounded text-[10px] font-semibold hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                                        >
                                          {verifyingBillId === bill.id ? (
                                            <><Loader2 className="w-2.5 h-2.5 animate-spin" /> Verifying</>
                                          ) : 'Verify'}
                                        </button>
                                        <button 
                                          onClick={() => handleRetryExtraction(bill.id)}
                                          disabled={retryingBillId === bill.id}
                                          className="p-1 border border-border-subtle rounded hover:bg-bg-primary text-text-secondary disabled:opacity-50"
                                          title="Retry AI Extraction"
                                        >
                                          <RefreshCw className={`w-3 h-3 ${retryingBillId === bill.id ? 'animate-spin' : ''}`} />
                                        </button>
                                      </>
                                    )}
                                    {isFailed && (
                                      <button 
                                        onClick={() => handleRetryExtraction(bill.id)}
                                        disabled={retryingBillId === bill.id}
                                        className="px-2 py-1 border border-red-500/30 hover:border-red-500 text-red-500 rounded text-[10px] font-semibold flex items-center gap-1 active:scale-95 transition-all disabled:opacity-50"
                                      >
                                        <RefreshCw className={`w-2.5 h-2.5 ${retryingBillId === bill.id ? 'animate-spin' : ''}`} />
                                        {retryingBillId === bill.id ? 'Retrying…' : 'Retry'}
                                      </button>
                                    )}
                                    {bill.status === 'verified' && (
                                      <span className="text-[10px] text-text-secondary px-1">Verified</span>
                                    )}
                                    {isProcessing && (
                                      <span className="text-[10px] text-text-secondary animate-pulse px-1">Running AI...</span>
                                    )}
                                    
                                    <button 
                                      onClick={() => setDeletingBillId(bill.id)}
                                      className="px-2 py-1 text-red-500 hover:text-red-600 rounded text-[10px] font-semibold transition-all active:scale-95"
                                      title="Delete Bill"
                                    >
                                      Delete
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                </div>
              ) : (
                <div className="flex flex-col items-center justify-center p-12 md:p-16 border border-dashed border-border-subtle rounded-lg bg-bg-secondary/10 text-center space-y-4">
                  <Building className="w-12 h-12 text-text-secondary opacity-50" />
                  <p className="font-mono text-sm text-text-secondary">No firm selected. Choose a client workspace from the header selector.</p>
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all flex items-center gap-2"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Client Firm
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: IMPORT-EXPORT */}
          {activeTab === 'import-export' && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-extrabold tracking-tight">Import-Export</h1>
                  <p className="text-sm text-text-secondary mt-1">Bill of Entry / Shipping Bill AI extraction and review grid.</p>
                </div>
              </div>

              {selectedFirm ? (
                <div className="space-y-8">

                  {/* Search + Status Filter */}
                  <div className="flex flex-wrap gap-4 items-center bg-bg-secondary p-4 border border-border-subtle rounded-md text-xs font-mono">
                    <div className="flex-1 min-w-[200px]">
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Search BE No / Shipper</label>
                      <input
                        type="text"
                        placeholder="Search..."
                        value={tradeDocSearch}
                        onChange={(e) => setTradeDocSearch(e.target.value)}
                        className="w-full bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">Status</label>
                      <select
                        value={tradeDocStatusFilter}
                        onChange={(e) => setTradeDocStatusFilter(e.target.value)}
                        className="bg-bg-primary border border-border-subtle rounded px-2.5 py-1.5 focus:outline-none focus:border-accent text-text-primary cursor-pointer"
                      >
                        <option value="">All Statuses</option>
                        <option value="processing">Processing</option>
                        <option value="needs_review">Needs Review</option>
                        <option value="verified">Verified</option>
                        <option value="extraction_failed">Failed</option>
                      </select>
                    </div>
                    <div className="ml-auto">
                      <label className="block text-[10px] text-text-secondary uppercase font-bold mb-1">&nbsp;</label>
                      <button
                        onClick={() => fetchTradeDocs({ manual: true })}
                        disabled={isRefreshingTradeDocs}
                        className="px-3 py-1.5 border border-border-subtle rounded hover:bg-bg-primary transition-colors flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 ${isRefreshingTradeDocs ? 'animate-spin' : ''}`} />
                        {isRefreshingTradeDocs ? 'Refreshing…' : 'Refresh'}
                      </button>
                    </div>
                  </div>

                  {/* Upload Drop Zone */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setIsDraggingTrade(true); }}
                    onDragLeave={() => setIsDraggingTrade(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDraggingTrade(false);
                      if (e.dataTransfer.files) handleTradeDocFilesSelected(e.dataTransfer.files);
                    }}
                    onClick={() => tradeDocInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-lg p-10 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all ${
                      isDraggingTrade
                        ? 'border-accent bg-accent/5 scale-[1.01]'
                        : 'border-border-subtle hover:border-text-primary/40 bg-bg-secondary/10'
                    }`}
                  >
                    <input
                      type="file"
                      ref={tradeDocInputRef}
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(e) => { if (e.target.files) handleTradeDocFilesSelected(e.target.files); }}
                      className="hidden"
                    />
                    <div className="w-12 h-12 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                      <Upload className="w-5 h-5" />
                    </div>
                    <div className="space-y-1 text-center">
                      <p className="font-mono text-sm font-semibold">Drag & drop Bills of Entry or click to browse</p>
                      <p className="text-xs text-text-secondary">PDF, JPG, PNG · max 10 MB per file</p>
                    </div>
                  </div>

                  {/* Upload progress */}
                  {(tradeDocUploadingFiles.length > 0 || tradeDocSummaryMsg) && (
                    <div className="border border-border-subtle rounded-lg bg-bg-secondary p-5 space-y-4">
                      {tradeDocSummaryMsg && (
                        <div className="text-xs font-mono text-text-primary font-bold flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-green-500" /> {tradeDocSummaryMsg}
                        </div>
                      )}
                      {tradeDocUploadingFiles.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-[10px] font-mono text-text-secondary uppercase tracking-wider font-bold">Uploading files...</h4>
                          {tradeDocUploadingFiles.map((file: any) => (
                            <div key={file.id} className="text-xs font-mono space-y-1">
                              <div className="flex justify-between text-text-secondary">
                                <span className="truncate max-w-xs">{file.name}</span>
                                <span>{file.progress}%</span>
                              </div>
                              <div className="w-full bg-bg-primary h-1.5 rounded overflow-hidden">
                                <div className="bg-accent h-1.5 transition-all duration-150" style={{ width: `${file.progress}%` }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Review Grid */}
                  {isInitialTradeDocsLoad && isLoadingTradeDocs ? (
                    <div className="border border-dashed border-border-subtle rounded-lg p-12 flex flex-col items-center justify-center gap-3 text-text-secondary font-mono text-xs bg-bg-secondary/10">
                      <Loader2 className="w-8 h-8 animate-spin text-text-primary" />
                      <p>Loading customs documents…</p>
                    </div>
                  ) : tradeDocs.length === 0 ? (
                    <div className="border border-dashed border-border-subtle rounded-lg p-12 text-center text-text-secondary bg-bg-secondary/10 flex flex-col items-center justify-center gap-4 font-mono text-xs">
                      <Globe className="w-10 h-10 opacity-40" />
                      <p>No customs documents uploaded yet.</p>
                      <button
                        onClick={() => tradeDocInputRef.current?.click()}
                        className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all flex items-center gap-2"
                      >
                        <Upload className="w-3.5 h-3.5" /> Upload Bill of Entry
                      </button>
                    </div>
                  ) : (
                    <div className="border border-border-subtle rounded-lg bg-bg-secondary overflow-x-auto shadow-sm">
                      <table className="w-full text-left border-collapse text-xs font-mono min-w-[900px]">
                        <thead>
                          <tr className="bg-bg-primary text-text-secondary border-b border-border-subtle text-[10px] uppercase font-bold tracking-wider">
                            <th className="p-2.5 border-r border-border-subtle min-w-[130px]">BE No</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[100px]">BE Date</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[160px]">Shipper</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[80px]">Port</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[120px]">Container ID</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[90px]">Gross KG</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[90px]">Net KG</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[130px]">Assessable Value</th>
                            <th className="p-2.5 border-r border-border-subtle min-w-[80px]">Status</th>
                            <th className="p-2.5 text-center min-w-[160px]">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tradeDocs
                            .filter((doc: any) => {
                              if (tradeDocStatusFilter && doc.status !== tradeDocStatusFilter) return false;
                              if (tradeDocSearch) {
                                const q = tradeDocSearch.toLowerCase();
                                return (
                                  (doc.be_number || '').toLowerCase().includes(q) ||
                                  (doc.shipper_name || '').toLowerCase().includes(q)
                                );
                              }
                              return true;
                            })
                            .map((doc: any) => {
                              const isProcessing = doc.status === 'processing';
                              const isFailed = doc.extraction_failed || doc.status === 'extraction_failed';
                              const rData = doc.raw_data || {};

                              const tradeCols = [
                                { field: 'be_number', val: doc.be_number || rData.be_number || '' },
                                { field: 'be_date', val: doc.be_date || rData.be_date || '' },
                                { field: 'shipper_name', val: doc.shipper_name || rData.shipper_name || '' },
                                { field: 'port_code', val: doc.port_code || rData.port_code || '' },
                                { field: 'container_id', val: doc.container_id || rData.container_id || '' },
                                { field: 'gross_weight', val: doc.gross_weight ?? rData.gross_weight ?? '', type: 'number' },
                                { field: 'net_weight', val: doc.net_weight ?? rData.net_weight ?? '', type: 'number' },
                                { field: 'assessable_value', val: doc.assessable_value ?? rData.assessable_value ?? '', type: 'number' },
                              ];

                              return (
                                <tr key={doc.id} className={`border-b border-border-subtle hover:bg-bg-primary/20 transition-colors ${
                                  savingTradeDocId === doc.id ? 'opacity-60' : ''
                                } ${
                                  isFailed ? 'bg-red-500/5' : isProcessing ? 'opacity-60' : ''
                                }`}>
                                  {tradeCols.map((cell) => {
                                    const isCellEditing = editingTradeCell?.docId === doc.id && editingTradeCell?.field === cell.field;
                                    return (
                                      <td
                                        key={cell.field}
                                        className="p-2 border-r border-border-subtle group cursor-text"
                                        onClick={() => {
                                          if (isProcessing || doc.status === 'verified') return;
                                          setEditingTradeCell({ docId: doc.id, field: cell.field });
                                          setEditTradeValue(String(cell.val));
                                        }}
                                      >
                                        {isCellEditing ? (
                                          <input
                                            autoFocus
                                            type={cell.type === 'number' ? 'number' : 'text'}
                                            value={editTradeValue}
                                            onChange={(e) => setEditTradeValue(e.target.value)}
                                            onBlur={() => handleTradeCellSave(doc.id, cell.field)}
                                            onKeyDown={(e) => {
                                              if (e.key === 'Enter' || e.key === 'Tab') handleTradeCellSave(doc.id, cell.field);
                                              if (e.key === 'Escape') setEditingTradeCell(null);
                                            }}
                                            className="w-full bg-bg-primary border border-accent rounded px-1.5 py-0.5 focus:outline-none text-text-primary"
                                          />
                                        ) : (
                                          <div className="flex items-center gap-1 min-h-[18px]">
                                            {isProcessing ? (
                                              <span className="text-text-secondary italic">extracting…</span>
                                            ) : (
                                              <span className="truncate max-w-[140px]" title={String(cell.val)}>{String(cell.val)}</span>
                                            )}
                                            {!isProcessing && doc.status !== 'verified' && (
                                              <Edit2 className="w-2.5 h-2.5 text-text-secondary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                                            )}
                                          </div>
                                        )}
                                      </td>
                                    );
                                  })}

                                  {/* Status Cell */}
                                  <td className="p-2 border-r border-border-subtle">
                                    <div className="flex items-center gap-1">
                                      {isProcessing && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-bg-primary border border-border-subtle text-text-secondary text-[9px] font-bold">
                                          <Loader2 className="w-2.5 h-2.5 animate-spin" /> Processing
                                        </span>
                                      )}
                                      {doc.status === 'needs_review' && !isFailed && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 text-[9px] font-bold">
                                          <Clock className="w-2.5 h-2.5" /> Review
                                        </span>
                                      )}
                                      {doc.status === 'verified' && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-green-500/10 border border-green-500/20 text-green-500 text-[9px] font-bold">
                                          <CheckCircle2 className="w-2.5 h-2.5" /> Verified
                                        </span>
                                      )}
                                      {isFailed && (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-red-500 text-[9px] font-bold">
                                          <AlertCircle className="w-2.5 h-2.5" /> Failed
                                        </span>
                                      )}
                                      {doc.validation_warnings?.length > 0 && !isProcessing && (
                                        <div className="relative group inline-block cursor-help">
                                          <span className="text-yellow-500 font-bold text-[11px]">&#9888;</span>
                                          <div className="absolute left-0 bottom-full mb-1.5 hidden group-hover:block z-50 bg-black text-white dark:bg-white dark:text-black p-2.5 rounded text-[10px] w-60 border border-border-subtle shadow-xl font-mono leading-relaxed pointer-events-none">
                                            <div className="font-bold border-b border-border-subtle pb-1 mb-1 flex items-center gap-1"><Info className="w-3 h-3 text-yellow-500" /> Warnings:</div>
                                            {doc.validation_warnings.map((w: string, idx: number) => (
                                              <div key={idx} className="mb-0.5">&bull; {w}</div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </td>

                                  {/* Actions Cell */}
                                  <td className="p-2 flex items-center justify-center gap-1.5">
                                    <button
                                      onClick={() => setViewingTradeDoc(doc)}
                                      className="px-2 py-1 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all active:scale-95"
                                    >
                                      View
                                    </button>

                                    {doc.status === 'needs_review' && (
                                      <button
                                        onClick={() => handleVerifyTradeDoc(doc.id)}
                                        disabled={verifyingTradeDocId === doc.id}
                                        className="px-2 py-1 bg-accent text-accent-foreground rounded text-[10px] font-bold hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1"
                                      >
                                        {verifyingTradeDocId === doc.id ? (
                                          <><Loader2 className="w-2.5 h-2.5 animate-spin" /> Verifying</>
                                        ) : 'Verify'}
                                      </button>
                                    )}

                                    {isFailed && (
                                      <button
                                        onClick={() => handleRetryTradeDoc(doc.id)}
                                        disabled={retryingTradeDocId === doc.id}
                                        className="px-2 py-1 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all active:scale-95 flex items-center gap-1 disabled:opacity-50"
                                      >
                                        <RefreshCw className={`w-2.5 h-2.5 ${retryingTradeDocId === doc.id ? 'animate-spin' : ''}`} />
                                        {retryingTradeDocId === doc.id ? 'Retrying…' : 'Retry'}
                                      </button>
                                    )}

                                    <button
                                      onClick={() => setDeletingTradeDocId(doc.id)}
                                      className="px-2 py-1 text-red-500 hover:text-red-600 rounded text-[10px] font-semibold transition-all active:scale-95"
                                    >
                                      Delete
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  )}

                </div>
              ) : (
                <div className="flex flex-col items-center justify-center p-12 md:p-16 border border-dashed border-border-subtle rounded-lg bg-bg-secondary/10 text-center space-y-4">
                  <Building className="w-12 h-12 text-text-secondary opacity-50" />
                  <p className="font-mono text-sm text-text-secondary">No firm selected. Choose a client workspace from the header selector.</p>
                  <button
                    onClick={() => setIsModalOpen(true)}
                    className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all flex items-center gap-2"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Client Firm
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: E-WAY BILLS */}
          {activeTab === 'e-way-bills' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight">E-way Bills</h1>
                <p className="text-sm text-text-secondary mt-1">Generate vehicle transit permits, calculate PIN-code distances, and verify transporter logs.</p>
              </div>

              <div className="border border-dashed border-border-subtle rounded-lg p-16 text-center bg-bg-secondary/10 flex flex-col items-center justify-center gap-6">
                <div className="w-12 h-12 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                  <Truck className="w-5 h-5" />
                </div>
                
                <div className="space-y-2 max-w-sm mx-auto">
                  <h3 className="text-lg font-bold">No transit bills generated</h3>
                  <p className="text-xs text-text-secondary font-mono leading-relaxed">
                    Verify compliance of active physical cargo transportation. Links automatically to GSTIN profiles.
                  </p>
                </div>

                <input 
                  type="file" 
                  ref={ewayBillsInputRef} 
                  onChange={(e) => handleStubFileUpload(e, 'eway_bills')} 
                  className="hidden" 
                  accept=".pdf,.jpg,.jpeg,.png,.xlsx"
                />
                <button 
                  onClick={() => ewayBillsInputRef.current?.click()}
                  disabled={isStubUploading}
                  className="px-6 py-2.5 bg-accent text-accent-foreground font-semibold rounded text-sm hover:opacity-90 active:scale-95 transition-all flex items-center gap-2 disabled:opacity-50"
                >
                  {isStubUploading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Uploading…</>
                  ) : (
                    <><Plus className="w-4 h-4" /> Generate E-Way Bill</>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* TAB 5: CLOUD VAULT */}
          {activeTab === 'vault' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight">Cloud Vault</h1>
                <p className="text-sm text-text-secondary mt-1">Secure index of source PDFs, spreadsheets, and tax audit records organized by upload date.</p>
              </div>

              {/* Breadcrumbs Navigation */}
              <div className="flex items-center gap-1.5 text-xs font-mono text-text-secondary border-b border-border-subtle pb-3 select-none">
                <span 
                  onClick={() => {
                    setSelectedVaultYear(null);
                    setSelectedVaultMonth(null);
                    setSelectedVaultDay(null);
                    setVaultFiles([]);
                  }}
                  className="hover:text-text-primary cursor-pointer font-bold transition-colors"
                >
                  Vault
                </span>
                {selectedVaultYear && (
                  <>
                    <span>&gt;</span>
                    <span 
                      onClick={() => {
                        setSelectedVaultMonth(null);
                        setSelectedVaultDay(null);
                        setVaultFiles([]);
                      }}
                      className="hover:text-text-primary cursor-pointer font-bold transition-colors"
                    >
                      {selectedVaultYear}
                    </span>
                  </>
                )}
                {selectedVaultMonth && (
                  <>
                    <span>&gt;</span>
                    <span 
                      onClick={() => {
                        setSelectedVaultDay(null);
                        setVaultFiles([]);
                      }}
                      className="hover:text-text-primary cursor-pointer font-bold transition-colors"
                    >
                      {getMonthName(selectedVaultMonth)}
                    </span>
                  </>
                )}
                {selectedVaultDay && (
                  <>
                    <span>&gt;</span>
                    <span className="text-text-primary font-bold">{selectedVaultDay}</span>
                  </>
                )}
              </div>

              {isLoadingVault ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3 font-mono text-xs text-text-secondary">
                  <Loader2 className="w-8 h-8 animate-spin text-text-primary" />
                  <p>Loading Vault Archive...</p>
                </div>
              ) : (
                <>
                  {/* LEVEL 1: YEAR SELECTION */}
                  {selectedVaultYear === null && (
                    <>
                      {vaultYears.length === 0 ? (
                        <div className="border border-dashed border-border-subtle rounded-lg p-16 text-center bg-bg-secondary/10 flex flex-col items-center justify-center gap-6">
                          <div className="w-12 h-12 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                            <FolderOpen className="w-5 h-5" />
                          </div>
                          <div className="space-y-2 max-w-sm mx-auto">
                            <h3 className="text-lg font-bold">Document vault is empty</h3>
                            <p className="text-xs text-text-secondary font-mono leading-relaxed">
                              Upload invoices on the Invoices tab or customs/transit bills to start building your date archive.
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2 justify-center">
                            <button
                              onClick={() => setActiveTab('invoices')}
                              className="px-4 py-2 bg-accent text-accent-foreground text-xs font-semibold rounded hover:opacity-90 transition-all"
                            >
                              Upload Invoices
                            </button>
                            <button
                              onClick={() => setActiveTab('import-export')}
                              className="px-4 py-2 border border-border-subtle text-xs font-semibold rounded hover:bg-bg-secondary transition-all"
                            >
                              Upload Customs Docs
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          {vaultYears.map((yr) => (
                            <div 
                              key={yr} 
                              onClick={() => {
                                setSelectedVaultYear(yr);
                                fetchVaultMonths(yr);
                              }}
                              className="border border-border-subtle rounded-lg p-6 bg-bg-secondary flex flex-col items-center justify-center gap-3 hover:border-text-primary/40 transition-all cursor-pointer font-mono hover:scale-[1.02] shadow-sm"
                            >
                              <div className="w-10 h-10 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                                <FolderOpen className="w-4 h-4" />
                              </div>
                              <div className="font-extrabold text-sm text-text-primary">{yr}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}

                  {/* LEVEL 2: MONTH SELECTION */}
                  {selectedVaultYear !== null && selectedVaultMonth === null && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      {vaultMonths.map((m) => (
                        <div 
                          key={m} 
                          onClick={() => {
                            setSelectedVaultMonth(m);
                            fetchVaultDays(selectedVaultYear, m);
                          }}
                          className="border border-border-subtle rounded-lg p-6 bg-bg-secondary flex flex-col items-center justify-center gap-3 hover:border-text-primary/40 transition-all cursor-pointer font-mono hover:scale-[1.02] shadow-sm"
                        >
                          <div className="w-10 h-10 rounded-full border border-border-subtle flex items-center justify-center bg-bg-primary text-text-secondary">
                            <Calendar className="w-4 h-4" />
                          </div>
                          <div className="font-extrabold text-sm text-text-primary">{getMonthName(m)}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* LEVEL 3: DAY SELECTION */}
                  {selectedVaultYear !== null && selectedVaultMonth !== null && selectedVaultDay === null && (
                    <div className="grid grid-cols-4 sm:grid-cols-8 gap-4">
                      {vaultDays.map((d) => (
                        <div 
                          key={d} 
                          onClick={() => {
                            setSelectedVaultDay(d);
                            fetchVaultDayFiles(selectedVaultYear, selectedVaultMonth, d, vaultModuleFilter);
                          }}
                          className="border border-border-subtle rounded-lg p-4 bg-bg-secondary flex flex-col items-center justify-center gap-2 hover:border-text-primary/40 transition-all cursor-pointer font-mono hover:scale-[1.02] shadow-sm"
                        >
                          <div className="text-xl font-extrabold text-text-primary">{d}</div>
                          <div className="text-[9px] text-text-secondary uppercase font-bold tracking-wider">Day</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* LEVEL 4: FILE LIST */}
                  {selectedVaultYear !== null && selectedVaultMonth !== null && selectedVaultDay !== null && (
                    <div className="space-y-4">
                      
                      {/* Module selection badges */}
                      <div className="flex flex-wrap gap-2 font-mono text-[9px]">
                        {[
                          { label: 'All Files', value: '' },
                          { label: 'Invoices', value: 'invoices' },
                          { label: 'Excel Exports', value: 'exports' },
                          { label: 'Customs Docs', value: 'import_export' },
                          { label: 'E-way Bills', value: 'eway_bills' }
                        ].map((mod) => (
                          <button
                            key={mod.value}
                            onClick={() => {
                              setVaultModuleFilter(mod.value);
                              fetchVaultDayFiles(selectedVaultYear, selectedVaultMonth, selectedVaultDay, mod.value);
                            }}
                            className={`px-2.5 py-1 border rounded transition-all font-semibold uppercase ${
                              vaultModuleFilter === mod.value 
                                ? 'bg-accent text-accent-foreground border-accent' 
                                : 'border-border-subtle hover:bg-bg-secondary text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            {mod.label}
                          </button>
                        ))}
                      </div>

                      {vaultFiles.length === 0 ? (
                        <div className="border border-dashed border-border-subtle rounded-lg p-12 text-center text-xs font-mono text-text-secondary bg-bg-secondary/5 flex flex-col items-center gap-4">
                          <p>No archived files match the selected filter.</p>
                          <button
                            onClick={() => {
                              setVaultModuleFilter('');
                              if (selectedVaultYear && selectedVaultMonth && selectedVaultDay) {
                                fetchVaultDayFiles(selectedVaultYear, selectedVaultMonth, selectedVaultDay, '');
                              }
                            }}
                            className="px-3 py-1.5 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all"
                          >
                            Clear Filter
                          </button>
                        </div>
                      ) : (
                        <div className="border border-border-subtle rounded-lg bg-bg-secondary overflow-x-auto shadow-sm">
                          <table className="w-full text-left border-collapse text-xs font-mono min-w-[750px]">
                            <thead>
                              <tr className="bg-bg-primary text-text-secondary border-b border-border-subtle text-[10px] uppercase font-bold tracking-wider">
                                <th className="p-3 border-r border-border-subtle">Original Filename</th>
                                <th className="p-3 border-r border-border-subtle min-w-[120px]">Module</th>
                                <th className="p-3 border-r border-border-subtle min-w-[100px]">Uploaded</th>
                                <th className="p-3 text-center min-w-[200px]">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {vaultFiles.map((entry) => (
                                <tr key={entry.id} className="border-b border-border-subtle hover:bg-bg-primary/10 transition-colors">
                                  <td className="p-3 border-r border-border-subtle font-semibold truncate max-w-xs" title={entry.file_name}>
                                    {entry.file_name}
                                  </td>
                                  <td className="p-3 border-r border-border-subtle">
                                    <span className={`inline-flex items-center px-1.5 py-0.25 rounded text-[9px] font-bold uppercase ${
                                      entry.module === 'invoices' ? 'bg-blue-500/10 border border-blue-500/20 text-blue-500' :
                                      entry.module === 'exports' ? 'bg-green-500/10 border border-green-500/20 text-green-500' :
                                      entry.module === 'import_export' ? 'bg-purple-500/10 border border-purple-500/20 text-purple-500' :
                                      'bg-yellow-500/10 border border-yellow-500/20 text-yellow-500'
                                    }`}>
                                      {entry.module === 'invoices' ? 'Invoice' :
                                       entry.module === 'exports' ? 'Excel Export' :
                                       entry.module === 'import_export' ? 'Customs' : 'E-Way Permit'}
                                    </span>
                                  </td>
                                  <td className="p-3 border-r border-border-subtle text-text-secondary">
                                    {new Date(entry.uploaded_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}
                                  </td>
                                  <td className="p-2 text-center flex items-center justify-center gap-1.5">
                                    <button
                                      onClick={() => handleDownloadExport(entry.file_url, entry.file_name)}
                                      className="px-2.5 py-1 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all active:scale-95"
                                    >
                                      Download
                                    </button>
                                    
                                    {entry.module === 'invoices' && entry.bill && (
                                      <button
                                        onClick={() => {
                                          setViewingBill(entry.bill);
                                          setActiveTab('invoices');
                                        }}
                                        className="px-2.5 py-1 border border-border-subtle rounded text-[10px] font-semibold hover:bg-bg-primary transition-all active:scale-95"
                                      >
                                        Edit
                                      </button>
                                    )}

                                    <button
                                      onClick={() => setDeletingVaultEntryId(entry.id)}
                                      className="px-2.5 py-1 text-red-500 hover:text-red-600 rounded text-[10px] font-semibold transition-all active:scale-95"
                                    >
                                      Delete
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* TAB 6: SETTINGS */}
          {activeTab === 'settings' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight">Settings</h1>
                <p className="text-sm text-text-secondary mt-1">Configure accountant profile credentials and developer API channels.</p>
              </div>

              <div className="border border-border-subtle rounded-lg bg-bg-secondary p-6">
                <form onSubmit={handleSaveSettings} className="space-y-6 max-w-md">
                  
                  {saveSuccess && (
                    <div className="p-3 bg-bg-primary border border-border-subtle text-xs font-mono rounded flex items-center gap-2 text-text-primary">
                      <UserCheck className="w-4 h-4 text-green-500" /> Settings updated successfully.
                    </div>
                  )}

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-mono text-text-secondary mb-1">Accountant Full Name</label>
                      <input
                        type="text"
                        value={accountantName}
                        onChange={(e) => setAccountantName(e.target.value)}
                        placeholder="e.g. Accountant Partner"
                        className="w-full px-3 py-2 bg-bg-primary border border-border-subtle rounded text-sm focus:outline-none focus:border-accent text-text-primary"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-mono text-text-secondary mb-1">Gemini Pro API Key (Override)</label>
                      <input
                        type="password"
                        value={geminiKey}
                        onChange={(e) => setGeminiKey(e.target.value)}
                        placeholder="••••••••••••••••••••••••"
                        className="w-full px-3 py-2 bg-bg-primary border border-border-subtle rounded text-sm focus:outline-none focus:border-accent text-text-primary font-mono"
                      />
                      <span className="text-[10px] text-text-secondary font-mono mt-1 block">
                        If provided, overrides system-level Gemini API settings.
                      </span>
                    </div>

                    <div>
                      <label className="block text-xs font-mono text-text-secondary mb-1">Active Email Address</label>
                      <input
                        type="email"
                        value={user?.email || ''}
                        disabled
                        className="w-full px-3 py-2 bg-bg-primary/50 border border-border-subtle rounded text-sm text-text-secondary focus:outline-none font-mono"
                      />
                    </div>
                  </div>

                  <div className="pt-4 border-t border-border-subtle">
                    <button
                      type="submit"
                      className="px-6 py-2.5 bg-accent text-accent-foreground font-semibold rounded text-sm hover:opacity-90 active:scale-95 transition-all"
                    >
                      Save Configurations
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

        </main>

        <SaasFooter variant="minimal" />
      </div>

      {/* Side-by-side File Viewer Modal */}
      {viewingBill && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 md:p-6 animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-subtle rounded-lg w-full max-w-6xl h-[90vh] md:h-[85vh] flex flex-col shadow-2xl overflow-hidden font-mono text-xs text-text-primary">
            
            {/* View Header */}
            <div className="h-14 border-b border-border-subtle px-6 flex justify-between items-center bg-bg-secondary">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-tight">Invoice Document Audit:</span>
                <span className="text-[10px] px-2 py-0.5 border border-border-subtle rounded bg-bg-primary text-text-secondary truncate max-w-xs">{viewingBill.file_name}</span>
              </div>
              <button 
                onClick={() => setViewingBill(null)}
                className="p-1 hover:bg-bg-primary rounded text-text-secondary hover:text-text-primary"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Side-by-side View */}
            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
              {/* Left Side: Original Document File preview */}
              <div className="w-full md:w-1/2 h-48 md:h-auto border-b md:border-b-0 md:border-r border-border-subtle bg-bg-secondary/40 flex items-center justify-center p-4">
                {viewingBill.file_name.toLowerCase().endsWith('.pdf') ? (
                  <iframe 
                    src={getFileUrl(viewingBill.file_url)} 
                    className="w-full h-full border-none rounded bg-bg-primary"
                    title="Invoice PDF"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-bg-secondary/20 rounded border border-border-subtle p-2 overflow-auto">
                    <img 
                      src={getFileUrl(viewingBill.file_url)} 
                      alt="Uploaded Invoice" 
                      className="max-w-full max-h-full object-contain"
                    />
                  </div>
                )}
              </div>

              {/* Right Side: Extracted Fields Review Form */}
              <div className="w-full md:w-1/2 overflow-y-auto p-4 md:p-6 space-y-6">
                <div className="space-y-1">
                  <h3 className="text-sm font-bold border-b border-border-subtle pb-2 uppercase text-text-secondary">Extracted Fields</h3>
                  <p className="text-[10px] text-text-secondary">Audit and verify the values parsed by AI. Click to edit values inline.</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: 'Invoice Number', field: 'invoice_number' },
                    { label: 'Invoice Date (YYYY-MM-DD)', field: 'invoice_date' },
                    { label: 'Party Name', field: 'party_name' },
                    { label: 'Party GSTIN', field: 'party_gstin' },
                    { label: 'Place of Supply', field: 'place_of_supply' },
                    { label: 'Taxable Amount (₹)', field: 'taxable_amount', type: 'number' },
                    { label: 'CGST (₹)', field: 'cgst', type: 'number' },
                    { label: 'SGST (₹)', field: 'sgst', type: 'number' },
                    { label: 'IGST (₹)', field: 'igst', type: 'number' },
                    { label: 'Cess (₹)', field: 'cess', type: 'number' },
                    { label: 'Total Amount (₹)', field: 'total_amount', type: 'number' },
                  ].map((item) => {
                    const val = viewingBill.raw_data?.[item.field] ?? '';
                    const isCellEditing = editingCell?.billId === viewingBill.id && editingCell?.field === item.field;

                    return (
                      <div key={item.field} className="space-y-1">
                        <label className="text-[10px] text-text-secondary uppercase font-bold">{item.label}</label>
                        {isCellEditing ? (
                          <input 
                            type="text" 
                            value={editValue} 
                            autoFocus
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={async () => {
                              await handleCellSave(viewingBill.id, item.field);
                              // Sync modal view
                              setViewingBill((prev: any) => ({
                                ...prev,
                                raw_data: { ...prev.raw_data, [item.field]: item.type === 'number' ? (parseFloat(editValue) || 0.0) : editValue }
                              }));
                            }}
                            onKeyDown={async (e) => {
                              if (e.key === 'Enter') {
                                await handleCellSave(viewingBill.id, item.field);
                                setViewingBill((prev: any) => ({
                                  ...prev,
                                  raw_data: { ...prev.raw_data, [item.field]: item.type === 'number' ? (parseFloat(editValue) || 0.0) : editValue }
                                }));
                              }
                            }}
                            className="w-full bg-bg-primary border border-accent rounded px-2 py-1.5 focus:outline-none"
                          />
                        ) : (
                          <div 
                            onClick={() => {
                              if (viewingBill.status !== 'verified') {
                                setEditingCell({ billId: viewingBill.id, field: item.field });
                                setEditValue(val.toString());
                              }
                            }}
                            className="w-full bg-bg-secondary hover:bg-bg-primary border border-border-subtle rounded px-2 py-1.5 cursor-pointer flex items-center justify-between text-xs"
                          >
                            <span className="truncate">{val}</span>
                            {viewingBill.status !== 'verified' && (
                              <Edit2 className="w-3 h-3 text-text-secondary opacity-50" />
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  <div className="space-y-1">
                    <label className="text-[10px] text-text-secondary uppercase font-bold">Bill Type</label>
                    <select
                      value={viewingBill.raw_data?.bill_type || 'purchase'}
                      disabled={viewingBill.status === 'verified'}
                      onChange={async (e) => {
                        setEditValue(e.target.value);
                        await handleCellSave(viewingBill.id, 'bill_type');
                        setViewingBill((prev: any) => ({
                          ...prev,
                          raw_data: { ...prev.raw_data, bill_type: e.target.value }
                        }));
                      }}
                      className="w-full bg-bg-secondary border border-border-subtle rounded px-2 py-1.5 focus:outline-none cursor-pointer"
                    >
                      <option value="purchase">Purchase</option>
                      <option value="sale">Sale</option>
                    </select>
                  </div>
                </div>

                {/* Validation warnings in Side Panel */}
                {viewingBill.validation_warnings?.length > 0 && (
                  <div className="border border-yellow-500/20 bg-yellow-500/5 rounded p-4 space-y-2">
                    <div className="flex items-center gap-1.5 text-yellow-500 font-bold">
                      <AlertCircle className="w-4.5 h-4.5" /> Validation Warnings
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-[10px] leading-relaxed text-text-secondary">
                      {viewingBill.validation_warnings.map((w: string, idx: number) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Status Display and Verification controls */}
                <div className="border-t border-border-subtle pt-6 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-text-secondary">Current Status:</span>
                    <span className="font-bold uppercase">{viewingBill.status}</span>
                  </div>
                  
                  <div className="flex gap-2">
                    {viewingBill.status === 'needs_review' && (
                      <button 
                        onClick={async () => {
                          await handleVerifyBill(viewingBill.id);
                          setViewingBill((prev: any) => ({ ...prev, status: 'verified' }));
                        }}
                        disabled={verifyingBillId === viewingBill.id}
                        className="px-4 py-2 bg-accent text-accent-foreground font-semibold rounded hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {verifyingBillId === viewingBill.id ? (
                          <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Verifying…</>
                        ) : 'Verify Invoice'}
                      </button>
                    )}
                    {viewingBill.status === 'extraction_failed' && (
                      <button 
                        onClick={async () => {
                          await handleRetryExtraction(viewingBill.id);
                          setViewingBill(null);
                        }}
                        disabled={retryingBillId === viewingBill.id}
                        className="px-4 py-2 bg-accent text-accent-foreground font-semibold rounded hover:opacity-90 active:scale-95 transition-all flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${retryingBillId === viewingBill.id ? 'animate-spin' : ''}`} />
                        {retryingBillId === viewingBill.id ? 'Retrying…' : 'Retry AI Extraction'}
                      </button>
                    )}
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deletingBillId !== null && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-subtle rounded-lg w-full max-w-sm p-6 shadow-2xl space-y-6 font-mono text-xs text-text-primary">
            <div className="space-y-2">
              <h3 className="text-base font-bold flex items-center gap-1.5 text-red-500">
                <AlertCircle className="w-5 h-5" /> Soft-Delete Invoice
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Are you sure you want to soft-delete this invoice? The record will be hidden from the workspace reports but remains recoverable. Unfinalized vault references will be cleared.
              </p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border-subtle pt-4">
              <button 
                onClick={() => setDeletingBillId(null)}
                className="px-3.5 py-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={async () => {
                  await handleDeleteBill(deletingBillId);
                  setDeletingBillId(null);
                }}
                disabled={isDeletingBill}
                className="px-3.5 py-2 bg-red-600 text-white font-semibold rounded hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1.5"
              >
                {isDeletingBill ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Deleting…</> : 'Delete Invoice'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Excel Export Outcome Modal */}
      {exportBatch && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-subtle rounded-lg w-full max-w-sm p-6 shadow-2xl space-y-6 font-mono text-xs text-text-primary">
            <div className="space-y-2">
              <h3 className="text-base font-bold flex items-center gap-1.5 text-text-primary">
                <CheckCircle2 className="w-5 h-5 text-green-500" /> Excel Sheet Generated
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Excel sheet batch <strong>{exportBatch.file_name}</strong> was created successfully containing {exportBatch.exported_count} transaction rows and saved to the Cloud Vault.
              </p>
            </div>
            
            <div className="flex justify-end gap-2 border-t border-border-subtle pt-4">
              <button 
                onClick={() => setExportBatch(null)}
                className="px-4 py-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              >
                Done
              </button>
              <button 
                onClick={() => handleDownloadExport(exportBatch.file_url, exportBatch.file_name)}
                className="px-4 py-2 bg-accent text-accent-foreground font-semibold rounded hover:opacity-90 active:scale-95 transition-all flex items-center gap-1.5"
              >
                Download File
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Excel Export Loading Spinner */}
      {isExporting && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-subtle rounded-lg w-full max-w-xs p-6 shadow-2xl space-y-4 font-mono text-xs text-text-primary text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-text-primary" />
            <p className="font-semibold">Generating Excel Ledger...</p>
            <p className="text-[10px] text-text-secondary">Structuring cells, calculating totals, and compiling sheets.</p>
          </div>
        </div>
      )}

      {/* Delete Vault Entry Confirmation Dialog */}
      {deletingVaultEntryId !== null && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-in fade-in duration-200">
          <div className="bg-bg-primary border border-border-subtle rounded-lg w-full max-w-sm p-6 shadow-2xl space-y-6 font-mono text-xs text-text-primary">
            <div className="space-y-2">
              <h3 className="text-base font-bold flex items-center gap-1.5 text-red-500">
                <AlertCircle className="w-5 h-5" /> Soft-Delete Document
              </h3>
              <p className="text-text-secondary leading-relaxed">
                Are you sure you want to soft-delete this vault document? The archived entry will be removed from your vault tree, and any underlying transaction records (bills/invoices) will also be soft-deleted.
              </p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border-subtle pt-4">
              <button 
                onClick={() => setDeletingVaultEntryId(null)}
                className="px-3.5 py-2 border border-border-subtle rounded hover:bg-bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={async () => {
                  await handleDeleteVaultEntry(deletingVaultEntryId);
                  setDeletingVaultEntryId(null);
                }}
                className="px-3.5 py-2 bg-red-600 text-white font-semibold rounded hover:opacity-90 active:scale-95 transition-all"
              >
                Delete Document
              </button>
            </div>
          </div>
        </div>
      )}

      <AddFirmModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
      />

      {/* ── Trade Doc: View Side Panel ── */}
      {viewingTradeDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-bg-secondary border border-border-subtle rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col text-text-primary">
            <div className="flex items-center justify-between p-5 border-b border-border-subtle">
              <div>
                <h3 className="font-bold text-lg">Trade Document — {viewingTradeDoc.file_name}</h3>
                <p className="text-xs font-mono text-text-secondary">Bill of Entry / Shipping Bill · status: {viewingTradeDoc.status}</p>
              </div>
              <button onClick={() => setViewingTradeDoc(null)} className="p-2 rounded hover:bg-bg-primary transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-1 flex-col md:flex-row overflow-hidden">
              {/* Left: file preview */}
              <div className="w-full md:w-1/2 h-48 md:h-auto border-b md:border-b-0 md:border-r border-border-subtle flex items-center justify-center bg-bg-primary p-4">
                {viewingTradeDoc.file_url && (
                  viewingTradeDoc.file_name?.toLowerCase().endsWith('.pdf') ? (
                    <iframe
                      src={getFileUrl(viewingTradeDoc.file_url)}
                      className="w-full h-full rounded bg-bg-primary border border-border-subtle"
                      title="Trade document preview"
                    />
                  ) : (
                    <img
                      src={getFileUrl(viewingTradeDoc.file_url)}
                      alt="Trade document"
                      className="max-w-full max-h-full object-contain rounded"
                    />
                  )
                )}
              </div>

              {/* Right: extracted fields */}
              <div className="w-full md:w-1/2 overflow-y-auto p-5 space-y-3 font-mono text-xs">
                <h4 className="font-bold text-sm mb-3">Extracted Fields</h4>
                {[
                  { label: 'BE Number', val: viewingTradeDoc.be_number || viewingTradeDoc.raw_data?.be_number },
                  { label: 'BE Date', val: viewingTradeDoc.be_date || viewingTradeDoc.raw_data?.be_date },
                  { label: 'Port Code', val: viewingTradeDoc.port_code || viewingTradeDoc.raw_data?.port_code },
                  { label: 'Container ID', val: viewingTradeDoc.container_id || viewingTradeDoc.raw_data?.container_id },
                  { label: 'Gross Weight (KG)', val: viewingTradeDoc.gross_weight ?? viewingTradeDoc.raw_data?.gross_weight },
                  { label: 'Net Weight (KG)', val: viewingTradeDoc.net_weight ?? viewingTradeDoc.raw_data?.net_weight },
                  { label: 'Currency', val: viewingTradeDoc.currency || viewingTradeDoc.raw_data?.currency },
                  { label: 'Assessable Value', val: viewingTradeDoc.assessable_value ?? viewingTradeDoc.raw_data?.assessable_value },
                  { label: 'Shipper Name', val: viewingTradeDoc.shipper_name || viewingTradeDoc.raw_data?.shipper_name },
                ].map(({ label, val }) => (
                  <div key={label} className="flex justify-between items-start border-b border-border-subtle pb-2 gap-4">
                    <span className="text-text-secondary shrink-0">{label}</span>
                    <span className="font-semibold text-right break-words">{val !== undefined && val !== null && val !== '' ? String(val) : '—'}</span>
                  </div>
                ))}
                {viewingTradeDoc.validation_warnings?.length > 0 && (
                  <div className="mt-4 p-3 rounded bg-yellow-500/10 border border-yellow-500/20 space-y-1">
                    <p className="font-bold text-yellow-500 flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" /> Validation Warnings</p>
                    {viewingTradeDoc.validation_warnings.map((w: string, i: number) => (
                      <p key={i} className="text-yellow-600 dark:text-yellow-400">&bull; {w}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Trade Doc: Delete Confirmation ── */}
      {deletingTradeDocId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-bg-secondary border border-border-subtle rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4 font-mono text-sm text-text-primary">
            <h3 className="font-bold text-lg flex items-center gap-2 text-red-500">
              <AlertCircle className="w-5 h-5" /> Delete Trade Document
            </h3>
            <p className="text-text-secondary leading-relaxed">
              This will soft-delete the trade document and remove its Cloud Vault entry. The record can be recovered by an administrator but will no longer appear in your workspace.
            </p>
            <div className="flex justify-end gap-2 border-t border-border-subtle pt-4">
              <button
                onClick={() => setDeletingTradeDocId(null)}
                className="px-3.5 py-2 border border-border-subtle rounded hover:bg-bg-primary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteTradeDoc(deletingTradeDocId)}
                disabled={isDeletingTradeDoc}
                className="px-3.5 py-2 bg-red-600 text-white font-semibold rounded hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1.5"
              >
                {isDeletingTradeDoc ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Deleting…</> : 'Delete Document'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
