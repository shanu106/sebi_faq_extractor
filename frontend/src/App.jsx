import { useState, useEffect } from 'react'
import {
  Search,
  Sliders,
  Filter,
  Database,
  CheckSquare,
  Clock,
  Layers,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
  TrendingUp,
  FileText,
  ChevronDown,
  ChevronUp,
  Info,
  Sparkles,
  Activity,
  Workflow,
  MessageSquareText,
  LayoutDashboard,
  Radio,
  ClipboardCheck,
  ScanSearch,
  ListTodo,
  FileBarChart2,
  Users,
  Settings,
  ScrollText,
  Check,
  LogOut,
  Lock
} from 'lucide-react'
import './App.css'

const API_BASE = 'https://sebi.nawaz.app/api/v1'

function App() {
  // Navigation & View states
  const [activeTab, setActiveTab] = useState('search') // maps to sidebar selections
  const [searchType, setSearchType] = useState('semantic') // 'semantic' | 'metadata' | 'fulltext' | 'combined'
  const [serverOnline, setServerOnline] = useState(false)

  // Search state parameters
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(10)
  const [minSimilarity, setMinSimilarity] = useState(0.4)
  const [semanticWeight, setSemanticWeight] = useState(0.6)
  const [fulltextWeight, setFulltextWeight] = useState(0.4)
  const [offset, setOffset] = useState(0)

  // Metadata Filters state
  const [department, setDepartment] = useState('')
  const [category, setCategory] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [complianceStatus, setComplianceStatus] = useState('')
  const [authority, setAuthority] = useState('')
  const [complianceFramework, setComplianceFramework] = useState('')
  const [isVerified, setIsVerified] = useState('') // '' | 'true' | 'false'
  const [useFiltersInCombined, setUseFiltersInCombined] = useState(true)

  // Results & Loading states
  const [results, setResults] = useState([])
  const [totalResults, setTotalResults] = useState(0)
  const [responseTime, setResponseTime] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [stats, setStats] = useState(null)
  const [analytics, setAnalytics] = useState(null)

  // Admin Authentication states
  const [adminToken, setAdminToken] = useState(localStorage.getItem('adminToken') || '')
  const [adminUsername, setAdminUsername] = useState(localStorage.getItem('adminUsername') || '')
  const [hasAdminSetup, setHasAdminSetup] = useState(true) // assume true until checked
  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [registerUsername, setRegisterUsername] = useState('')
  const [registerPassword, setRegisterPassword] = useState('')
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState('')
  const [authError, setAuthError] = useState(null)
  const [authLoading, setAuthLoading] = useState(false)

  const checkAdminSetup = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/check`)
      if (res.ok) {
        const data = await res.json()
        setHasAdminSetup(data.has_admin)
      }
    } catch (e) {
      console.error('Failed to check admin setup', e)
    }
  }

  const handleAdminLogin = async (e) => {
    if (e) e.preventDefault()
    setAuthError(null)
    setAuthLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: loginUsername,
          password: loginPassword
        })
      })
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Login failed')
      }
      const data = await response.json()
      localStorage.setItem('adminToken', data.access_token)
      localStorage.setItem('adminUsername', loginUsername)
      setAdminToken(data.access_token)
      setAdminUsername(loginUsername)
      setLoginUsername('')
      setLoginPassword('')
      setAuthError(null)
    } catch (err) {
      setAuthError(err.message)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleAdminRegister = async (e) => {
    if (e) e.preventDefault()
    setAuthError(null)
    if (registerPassword !== registerPasswordConfirm) {
      setAuthError("Passwords do not match")
      return
    }
    setAuthLoading(true)
    try {
      const response = await fetch(`${API_BASE}/auth/register-admin`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: registerUsername,
          password: registerPassword
        })
      })
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Registration failed')
      }
      const data = await response.json()
      localStorage.setItem('adminToken', data.access_token)
      localStorage.setItem('adminUsername', registerUsername)
      setAdminToken(data.access_token)
      setAdminUsername(registerUsername)
      setRegisterUsername('')
      setRegisterPassword('')
      setRegisterPasswordConfirm('')
      setHasAdminSetup(true)
      setAuthError(null)
    } catch (err) {
      setAuthError(err.message)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleAdminLogout = async () => {
    try {
      if (adminToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${adminToken}`
          }
        })
      }
    } catch (e) {
      console.error("Logout API failed", e)
    } finally {
      localStorage.removeItem('adminToken')
      localStorage.removeItem('adminUsername')
      setAdminToken('')
      setAdminUsername('')
      setStats(null)
      setAnalytics(null)
      setActiveTab('search')
    }
  }


  // Detail accordion cache
  const [expandedFaqId, setExpandedFaqId] = useState(null)
  const [faqDetails, setFaqDetails] = useState({}) // faqId -> detail response
  const [showHistorical, setShowHistorical] = useState({}) // faqId -> boolean

  // Excel extract states
  const [selectedFile, setSelectedFile] = useState(null)
  const [extractLoading, setExtractLoading] = useState(false)
  const [extractResult, setExtractResult] = useState(null)
  const [extractError, setExtractError] = useState(null)

  const handleExcelExtract = async () => {
    if (!selectedFile) return
    setExtractLoading(true)
    setExtractError(null)
    setExtractResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE}/faqs/extract-excel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`
        },
        body: formData,
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to process Excel file')
      }

      const data = await response.json()
      setExtractResult(data)
      // Refresh stats
      fetchStats()
    } catch (err) {
      setExtractError(err.message)
    } finally {
      setExtractLoading(false)
    }
  }

  // Excel metadata update states
  const [selectedMetaFile, setSelectedMetaFile] = useState(null)
  const [metaLoading, setMetaLoading] = useState(false)
  const [metaResult, setMetaResult] = useState(null)
  const [metaError, setMetaError] = useState(null)

  const handleMetadataUpdate = async () => {
    if (!selectedMetaFile) return
    setMetaLoading(true)
    setMetaError(null)
    setMetaResult(null)

    const formData = new FormData()
    formData.append('file', selectedMetaFile)

    try {
      const response = await fetch(`${API_BASE}/faqs/update-metadata`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`
        },
        body: formData,
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to update metadata')
      }

      const data = await response.json()
      setMetaResult(data)
      // Refresh stats
      fetchStats()
    } catch (err) {
      setMetaError(err.message)
    } finally {
      setMetaLoading(false)
    }
  }

  // Single PDF Ingestion states
  const [pdfSourceType, setPdfSourceType] = useState('file') // 'file' | 'link'
  const [selectedPdfFile, setSelectedPdfFile] = useState(null)
  const [pdfUrlInput, setPdfUrlInput] = useState('')
  const [pdfCategory, setPdfCategory] = useState('')
  const [pdfTopic, setPdfTopic] = useState('')
  const [pdfSubtopic, setPdfSubtopic] = useState('')
  const [pdfDate, setPdfDate] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfResult, setPdfResult] = useState(null)
  const [pdfError, setPdfError] = useState(null)

  const handlePdfExtract = async () => {
    if (pdfSourceType === 'file' && !selectedPdfFile) return
    if (pdfSourceType === 'link' && !pdfUrlInput.trim()) return

    setPdfLoading(true)
    setPdfError(null)
    setPdfResult(null)

    const formData = new FormData()
    if (pdfSourceType === 'file') {
      formData.append('file', selectedPdfFile)
    } else {
      formData.append('pdf_url', pdfUrlInput.trim())
    }

    if (pdfCategory.trim()) formData.append('category', pdfCategory.trim())
    if (pdfTopic.trim()) formData.append('topic', pdfTopic.trim())
    if (pdfSubtopic.trim()) formData.append('subtopic', pdfSubtopic.trim())
    if (pdfDate.trim()) formData.append('document_publish_date', pdfDate.trim())

    try {
      const response = await fetch(`${API_BASE}/faqs/extract-pdf`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`
        },
        body: formData,
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to process PDF')
      }

      const data = await response.json()
      setPdfResult(data)
      // Refresh stats
      fetchStats()
    } catch (err) {
      setPdfError(err.message)
    } finally {
      setPdfLoading(false)
    }
  }

  // Pre-configured options from database
  const departments = [
    'Compliance & General', 'Corporate Governance', 'Intermediaries',
    'Investor Protection', 'Listing & Disclosures', 'Market Operations',
    'Mutual Funds', 'Research'
  ]

  const categories = [
    'Comprehensive FAQs on SEBI (PIT) Regulations, 2015',
    'FAQ - General',
    'FAQ - Portfolio Managers',
    'FAQ-Open offer, Buyback Offer and Delisting Offers',
    'FAQs - Business Responsibility Reports',
    'FAQs - Equity and Currency Derivatives',
    'FAQs - Takeover',
    'FAQs for Mutual Fund Intermediaries',
    'FAQs for Mutual Fund Investors',
    'FAQs on Framework for Small and Medium REITs (SM REITs)',
    'FAQs on ICDR Regulations 2018',
    'FAQs on Infrastructure Investment Trusts (InvITs)',
    'FAQs on LODR Regulations 2015',
    'FAQs on Real Estate Investment Trusts (REITs)',
    'FAQs on SEBI (Buyback of Securities) Regulations, 2018',
    'FAQs on SEBI (Delisting of Equity Shares) Regulations, 2021',
    'Frequently Asked Questions (FAQs) on Cybersecurity and Cyber Resilience Framework (CSCRF) for SEBI R',
    'Frequently Asked Questions (FAQs) on SEBI Registered Investment Advisers'
  ]

  const riskLevels = ['high', 'medium', 'low']
  const complianceStatuses = ['mandatory', 'recommended', 'informational']

  // Check server status
  const checkServer = async () => {
    try {
      const res = await fetch('https://sebi.nawaz.app/health')
      if (res.ok) {
        setServerOnline(true)
      } else {
        setServerOnline(false)
      }
    } catch {
      setServerOnline(false)
    }
  }

  const handleLogoutLocal = () => {
    localStorage.removeItem('adminToken')
    localStorage.removeItem('adminUsername')
    setAdminToken('')
    setAdminUsername('')
    setStats(null)
    setAnalytics(null)
    setActiveTab('search')
  }

  // Fetch coverage stats and search log analytics
  const fetchStats = async () => {
    if (!adminToken) return
    try {
      const statsRes = await fetch(`${API_BASE}/stats/faqs`, {
        headers: {
          'Authorization': `Bearer ${adminToken}`
        }
      })
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData)
      } else if (statsRes.status === 401) {
        handleLogoutLocal()
        return
      }

      const analyticsRes = await fetch(`${API_BASE}/stats/searches?days=7`, {
        headers: {
          'Authorization': `Bearer ${adminToken}`
        }
      })
      if (analyticsRes.ok) {
        const analyticsData = await analyticsRes.json()
        setAnalytics(analyticsData)
      }
    } catch (e) {
      console.error('Failed to load stats/analytics', e)
    }
  }

  useEffect(() => {
    checkServer()
    checkAdminSetup()
    const interval = setInterval(checkServer, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (adminToken) {
      fetchStats()
    }
  }, [adminToken])


  // Execute Search
  const handleSearch = async (e) => {
    if (e) e.preventDefault()

    // Checks & validations
    if (searchType !== 'metadata' && (!query || query.trim().length < 3)) {
      setError('Search query must be at least 3 characters long.')
      return
    }

    setLoading(true)
    setError(null)
    setExpandedFaqId(null)

    let endpoint = ''
    let body = {}

    try {
      if (searchType === 'semantic') {
        endpoint = `${API_BASE}/search/semantic`
        body = {
          query: query.trim(),
          limit: parseInt(limit),
          min_similarity: parseFloat(minSimilarity)
        }
      } else if (searchType === 'fulltext') {
        endpoint = `${API_BASE}/search/fulltext`
        body = {
          query: query.trim(),
          limit: parseInt(limit)
        }
      } else if (searchType === 'metadata') {
        endpoint = `${API_BASE}/search/metadata`
        body = {}
        if (department) body.department = department
        if (category) body.category = category
        if (riskLevel) body.risk_level = riskLevel
        if (complianceStatus) body.compliance_status = complianceStatus
        if (authority) body.authority = authority
        if (complianceFramework) body.compliance_framework = complianceFramework
        if (isVerified) body.is_verified = isVerified === 'true'
      } else if (searchType === 'combined') {
        endpoint = `${API_BASE}/search/combined`

        let metaFilters = null
        if (useFiltersInCombined && (department || category || riskLevel || complianceStatus || authority || complianceFramework || isVerified)) {
          metaFilters = {}
          if (department) metaFilters.department = department
          if (category) metaFilters.category = category
          if (riskLevel) metaFilters.risk_level = riskLevel
          if (complianceStatus) metaFilters.compliance_status = complianceStatus
          if (authority) metaFilters.authority = authority
          if (complianceFramework) metaFilters.compliance_framework = complianceFramework
          if (isVerified) metaFilters.is_verified = isVerified === 'true'
        }

        body = {
          query: query.trim(),
          semantic_weight: parseFloat(semanticWeight),
          fulltext_weight: parseFloat(fulltextWeight),
          min_similarity: parseFloat(minSimilarity),
          limit: parseInt(limit),
          offset: parseInt(offset),
          metadata_filters: metaFilters
        }
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to search')
      }

      const data = await response.json()
      setResults(data.results || [])
      setTotalResults(data.total_results || 0)
      setResponseTime(data.response_time_ms || 0)

      // Refresh stats & log analytics
      fetchStats()
    } catch (err) {
      setError(err.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  // Lazy load checklist and related faq details
  const handleToggleExpand = async (faqId) => {
    if (expandedFaqId === faqId) {
      setExpandedFaqId(null)
      return
    }

    setExpandedFaqId(faqId)

    if (!faqDetails[faqId]) {
      try {
        const res = await fetch(`${API_BASE}/faqs/${faqId}`)
        if (res.ok) {
          const data = await res.json()
          setFaqDetails(prev => ({
            ...prev,
            [faqId]: data
          }))
        }
      } catch (err) {
        console.error('Error fetching FAQ details:', err)
      }
    }
  }

  // Clear filters
  const resetFilters = () => {
    setDepartment('')
    setCategory('')
    setRiskLevel('')
    setComplianceStatus('')
    setAuthority('')
    setComplianceFramework('')
    setIsVerified('')
  }

  // Navigation Items (Matching compliancer-frontend Sidebar)
  const workNav = [
    { id: 'operations', icon: Sparkles, label: 'Operations' },
    { id: 'monitoring', icon: Activity, label: 'Monitoring' },
    { id: 'agent-studio', icon: Workflow, label: 'Agent Studio' },
    { id: 'search', icon: MessageSquareText, label: 'Ask Compliance' } // FAQ search tab
  ]

  const intelligenceNav = [
    { id: 'command', icon: LayoutDashboard, label: 'Command Centre' },
    { id: 'extract', icon: Radio, label: 'Regulatory Monitor' }, // Excel PDF extraction tab
    { id: 'assess', icon: ClipboardCheck, label: 'Assess' },
    { id: 'process-audit', icon: ScanSearch, label: 'Process Audit' },
    { id: 'workflow', icon: ListTodo, label: 'Workflow' },
    { id: 'reports', icon: FileBarChart2, label: 'Reports' }
  ]

  const utilityNav = [
    { id: 'team', icon: Users, label: 'Team' },
    { id: 'settings', icon: Settings, label: 'Settings' },
    { id: 'analytics', icon: ScrollText, label: 'Audit Log' }, // Analytics tab
    { id: 'help', icon: HelpCircle, label: 'Help' }
  ]

  // Get active tab label for header
  const getActiveTabLabel = () => {
    const allNavs = [...workNav, ...intelligenceNav, ...utilityNav]
    const item = allNavs.find(n => n.id === activeTab)
    return item ? item.label : 'Dashboard'
  }

  const renderLoginView = () => {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '500px', width: '100%' }}>
        <div className="stat-card" style={{ maxWidth: '400px', width: '100%', padding: '2.5rem', background: '#FFFFFF', border: '1px solid #D8E0EA', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--primary-color)', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Lock size={22} />
            </div>
          </div>
          
          <h2 style={{ textAlign: 'center', fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            {hasAdminSetup ? 'Administrator Sign In' : 'First-Time Admin Setup'}
          </h2>
          <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '2rem' }}>
            {hasAdminSetup 
              ? 'Provide credentials to access regulatory monitor and audit logs.' 
              : 'Configure the root administrator account. This can only be done once.'}
          </p>

          {authError && (
            <div style={{ background: '#FEE2E2', border: '1px solid #FCA5A5', color: '#B91C1C', padding: '0.75rem', borderRadius: '8px', fontSize: '12px', marginBottom: '1.5rem', textAlign: 'center' }}>
              {authError}
            </div>
          )}

          {hasAdminSetup ? (
            <form onSubmit={handleAdminLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Username</label>
                <input 
                  type="text" 
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="Enter admin username"
                  required
                  style={{ width: '100%', padding: '0.65rem 0.85rem', border: '1px solid #D8E0EA', borderRadius: '8px', fontSize: '13px', background: '#F8FAFC' }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Password</label>
                <input 
                  type="password" 
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="Enter admin password"
                  required
                  style={{ width: '100%', padding: '0.65rem 0.85rem', border: '1px solid #D8E0EA', borderRadius: '8px', fontSize: '13px', background: '#F8FAFC' }}
                />
              </div>
              <button 
                type="submit" 
                disabled={authLoading}
                className="nav-item-btn active"
                style={{ width: '100%', padding: '0.75rem', border: 'none', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem' }}
              >
                {authLoading ? 'Signing In...' : 'Authenticate'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleAdminRegister} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Username</label>
                <input 
                  type="text" 
                  value={registerUsername}
                  onChange={(e) => setRegisterUsername(e.target.value)}
                  placeholder="Create admin username"
                  required
                  style={{ width: '100%', padding: '0.65rem 0.85rem', border: '1px solid #D8E0EA', borderRadius: '8px', fontSize: '13px', background: '#F8FAFC' }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Password</label>
                <input 
                  type="password" 
                  value={registerPassword}
                  onChange={(e) => setRegisterPassword(e.target.value)}
                  placeholder="Create admin password"
                  required
                  style={{ width: '100%', padding: '0.65rem 0.85rem', border: '1px solid #D8E0EA', borderRadius: '8px', fontSize: '13px', background: '#F8FAFC' }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>Confirm Password</label>
                <input 
                  type="password" 
                  value={registerPasswordConfirm}
                  onChange={(e) => setRegisterPasswordConfirm(e.target.value)}
                  placeholder="Confirm admin password"
                  required
                  style={{ width: '100%', padding: '0.65rem 0.85rem', border: '1px solid #D8E0EA', borderRadius: '8px', fontSize: '13px', background: '#F8FAFC' }}
                />
              </div>
              <button 
                type="submit" 
                disabled={authLoading}
                className="nav-item-btn active"
                style={{ width: '100%', padding: '0.75rem', border: 'none', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem' }}
              >
                {authLoading ? 'Registering...' : 'Create Admin Account'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  // Mock Core Efficore Page wrapper
  const renderPlaceholder = (id) => {
    const allNavs = [...workNav, ...intelligenceNav, ...utilityNav]
    const item = allNavs.find(n => n.id === id)
    const label = item ? item.label : 'Feature'
    const Icon = item ? item.icon : Sparkles

    return (
      <div className="empty-state" style={{ minHeight: '420px', padding: '3.5rem', background: '#FFFFFF', border: '1px solid #D8E0EA' }}>
        <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(49, 46, 129, 0.06)', color: '#312E81', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.5rem' }}>
          <Icon size={28} />
        </div>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0B1E3B', marginBottom: '0.5rem' }}>{label} Dashboard</h3>
        <p style={{ color: '#374151', fontSize: '0.85rem', maxWidth: '460px', lineHeight: 1.6, marginBottom: '1.5rem' }}>
          This capability is a core service of the Efficore Platform. To interact with the SEBI FAQ intelligent retrieval engine, please select **Ask Compliance** or **Regulatory Monitor** from the sidebar list.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <span className="chip" style={{ background: '#F0FDF4', color: '#16A34A', borderColor: '#BBF7D0' }}>Active Sandbox</span>
          <span className="chip" style={{ background: '#EFF6FF', color: '#1E3A8A', borderColor: '#BFDBFE' }}>Efficore Core</span>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      {/* Sidebar Nav */}
      <aside className="sidebar">
        {/* Brand */}
        <div className="sidebar-brand-section">
          <div className="sidebar-brand-logo">
            <img src="/mark-white.svg" alt="" aria-hidden="true" style={{ width: '28px', height: '28px' }} />
            <span className="sidebar-brand-text">Efficore</span>
          </div>
          <div className="sidebar-status-badge">
            <span className="status-dot pulse"></span>
            <span style={{ fontSize: '9px', fontWeight: 'bold' }}>Live Demo</span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="sidebar-nav-container">
          {/* Operations */}
          <div>
            <h4 className="sidebar-nav-section-title">Operations</h4>
            <ul className="sidebar-nav-list">
              {workNav.map(item => (
                <li key={item.id}>
                  <button
                    className={`nav-item-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    <item.icon className="nav-item-icon" />
                    <span>{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Intelligence */}
          <div>
            <h4 className="sidebar-nav-section-title">Intelligence</h4>
            <ul className="sidebar-nav-list">
              {intelligenceNav.map(item => (
                <li key={item.id}>
                  <button
                    className={`nav-item-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    <item.icon className="nav-item-icon" />
                    <span>{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Utility */}
          <div>
            <h4 className="sidebar-nav-section-title">System</h4>
            <ul className="sidebar-nav-list">
              {utilityNav.map(item => (
                <li key={item.id}>
                  <button
                    className={`nav-item-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    <item.icon className="nav-item-icon" />
                    <span>{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </nav>

        {/* Sidebar Footer User Info */}
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">
              {adminToken ? adminUsername.substring(0, 2).toUpperCase() : 'GU'}
            </div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">
                {adminToken ? adminUsername : 'Guest User'}
              </div>
              <div className="sidebar-user-role">
                {adminToken ? 'System Administrator' : 'Public Viewer'}
              </div>
            </div>
            {adminToken && (
              <button 
                className="sidebar-logout-btn" 
                title="Sign Out"
                onClick={handleAdminLogout}
              >
                <LogOut size={14} />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Panel */}
      <div className="main-panel">
        {/* Topbar Header */}
        <header className="top-header">
          <div className="top-header-title">
            <h2>{getActiveTabLabel()}</h2>
            <span style={{ fontSize: '12px' }}>• SEBI FAQ Intelligent Retrieval Core</span>
          </div>

          <div className="api-status-pill">
            <span className={`api-status-dot ${serverOnline ? 'online' : ''}`}></span>
            <span>API Server: {serverOnline ? 'Connected' : 'Offline'}</span>
          </div>
        </header>

        {/* Content Container */}
        <main className="main-content">
          {/* 1. QUERY SEARCH TAB (Ask Compliance) */}
          {activeTab === 'search' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {/* Realtime stats row */}
              {stats && (
                <div className="stats-grid">
                  <div className="stat-card">
                    <span className="stat-label">Total Ingested Obligations</span>
                    <span className="stat-val">{stats.total_faqs}</span>
                    <span className="stat-sub">Active regulatory FAQ entries</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Verified Compliance Items</span>
                    <span className="stat-val">{stats.verified_faqs}</span>
                    <span className="stat-sub">Audited & approved</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Unverified Pending Audit</span>
                    <span className="stat-val">{stats.total_faqs - stats.verified_faqs}</span>
                    <span className="stat-sub">Under regulatory review</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Vector Retrieve Latency</span>
                    <span className="stat-val">
                      {analytics ? `${analytics.average_response_time_ms.toFixed(1)}` : '0.0'}
                      <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)' }}> ms</span>
                    </span>
                    <span className="stat-sub">Qdrant retrieve + SQL join</span>
                  </div>
                </div>
              )}

              {/* Main Dashboard split column */}
              <div className="dashboard-container">
                {/* Sidebar Parameters panel card */}
                <aside className="sidebar-controls-card">
                  <div>
                    <h3 className="section-title">Retrieval Mode</h3>
                    <select
                      className="form-select"
                      value={searchType}
                      onChange={(e) => {
                        setSearchType(e.target.value)
                        setError(null)
                      }}
                    >
                      <option value="semantic">Semantic Search (Meaning)</option>
                      <option value="combined">Combined (Hybrid + Weights)</option>
                      <option value="fulltext">Full-Text (Keywords)</option>
                      <option value="metadata">Metadata Filter Only</option>
                    </select>
                  </div>

                  {/* Textarea query input inside sidebar parameters */}
                  {searchType !== 'metadata' && (
                    <div className="form-group">
                      <label>Regulatory Query</label>
                      <textarea
                        className="form-input"
                        style={{ height: '70px', resize: 'none', fontSize: '13px' }}
                        placeholder="Enter regulatory query or compliance topic..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </div>
                  )}

                  {/* Sliders Panel */}
                  {searchType !== 'metadata' && (
                    <div>
                      <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Sliders size={13} style={{ color: 'var(--accent-teal)' }} /> Search Configurations
                      </h3>

                      <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                        <label>
                          Results Limit
                          <span className="label-val">{limit}</span>
                        </label>
                        <div className="slider-container">
                          <input
                            type="range"
                            min="1"
                            max="50"
                            value={limit}
                            onChange={(e) => setLimit(e.target.value)}
                          />
                        </div>
                      </div>

                      {(searchType === 'semantic' || searchType === 'combined') && (
                        <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                          <label>
                            Similarity Cutoff
                            <span className="label-val">{minSimilarity}</span>
                          </label>
                          <div className="slider-container">
                            <input
                              type="range"
                              min="0.0"
                              max="1.0"
                              step="0.05"
                              value={minSimilarity}
                              onChange={(e) => setMinSimilarity(parseFloat(e.target.value))}
                            />
                          </div>
                        </div>
                      )}

                      {searchType === 'combined' && (
                        <>
                          <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                            <label>
                              Semantic Weight
                              <span className="label-val">{semanticWeight}</span>
                            </label>
                            <div className="slider-container">
                              <input
                                type="range"
                                min="0.0"
                                max="1.0"
                                step="0.1"
                                value={semanticWeight}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value)
                                  setSemanticWeight(val)
                                  setFulltextWeight(parseFloat((1.0 - val).toFixed(1)))
                                }}
                              />
                            </div>
                          </div>

                          <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                            <label>
                              Fulltext Weight
                              <span className="label-val">{fulltextWeight}</span>
                            </label>
                            <div className="slider-container">
                              <input
                                type="range"
                                min="0.0"
                                max="1.0"
                                step="0.1"
                                value={fulltextWeight}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value)
                                  setFulltextWeight(val)
                                  setSemanticWeight(parseFloat((1.0 - val).toFixed(1)))
                                }}
                              />
                            </div>
                          </div>

                          <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                            <label>Pagination Offset</label>
                            <input
                              type="number"
                              className="form-input"
                              min="0"
                              value={offset}
                              onChange={(e) => setOffset(Math.max(0, parseInt(e.target.value) || 0))}
                              style={{ padding: '0.4rem 0.6rem', fontSize: '12px' }}
                            />
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Metadata Filters Card */}
                  {(searchType === 'metadata' || searchType === 'combined') && (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <h3 className="section-title" style={{ margin: 0 }}>Metadata Filters</h3>
                        <button
                          style={{ background: 'none', border: 'none', color: 'var(--accent-teal)', fontSize: '11px', fontWeight: 'bold', cursor: 'pointer' }}
                          onClick={resetFilters}
                        >
                          Reset
                        </button>
                      </div>

                      {searchType === 'combined' && (
                        <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                          <label className="checkbox-group">
                            <input
                              type="checkbox"
                              checked={useFiltersInCombined}
                              onChange={(e) => setUseFiltersInCombined(e.target.checked)}
                            />
                            Apply filters to search
                          </label>
                        </div>
                      )}

                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>Department</label>
                        <select
                          className="form-select"
                          value={department}
                          onChange={(e) => setDepartment(e.target.value)}
                        >
                          <option value="">-- All --</option>
                          {departments.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                      </div>

                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>Category</label>
                        <select
                          className="form-select"
                          value={category}
                          onChange={(e) => setCategory(e.target.value)}
                        >
                          <option value="">-- All --</option>
                          {categories.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                      </div>

                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>Risk Level</label>
                        <select
                          className="form-select"
                          value={riskLevel}
                          onChange={(e) => setRiskLevel(e.target.value)}
                        >
                          <option value="">-- All --</option>
                          {riskLevels.map(r => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </div>

                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>Compliance Status</label>
                        <select
                          className="form-select"
                          value={complianceStatus}
                          onChange={(e) => setComplianceStatus(e.target.value)}
                        >
                          <option value="">-- All --</option>
                          {complianceStatuses.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>

                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>Verification Status</label>
                        <select
                          className="form-select"
                          value={isVerified}
                          onChange={(e) => setIsVerified(e.target.value)}
                        >
                          <option value="">-- All --</option>
                          <option value="true">Verified FAQs</option>
                          <option value="false">Unverified FAQs</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* Run Query Button */}
                  <button
                    className="btn-search"
                    onClick={handleSearch}
                    disabled={loading || (!serverOnline && !results.length)}
                  >
                    <Search size={14} />
                    {loading ? 'Retrieving...' : 'Run Retrieve Query'}
                  </button>

                  {error && (
                    <div style={{ color: 'var(--chip-critical-fg)', fontSize: '11px', display: 'flex', gap: '0.4rem', background: 'var(--chip-critical-bg)', padding: '0.6rem', borderRadius: '6px', border: '1px solid var(--chip-critical-br)' }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>{error}</span>
                    </div>
                  )}
                </aside>

                {/* Results Column */}
                <div className="results-column">
                  <div className="results-meta">
                    <h3>Compliance Results</h3>
                    <span>
                      {results.length > 0 && `Found ${totalResults} obligations (took ${responseTime.toFixed(1)}ms)`}
                    </span>
                  </div>

                  {loading ? (
                    <div className="spinner-container">
                      <div className="spinner"></div>
                      <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Querying vector databases and linking schemas...</p>
                    </div>
                  ) : results.length > 0 ? (
                    <div className="results-list">
                      {results.map((result, idx) => {
                        const faq = result.faq
                        const isExpanded = expandedFaqId === faq.id
                        const detail = faqDetails[faq.id]

                        return (
                          <div key={faq.id} className="faq-card">
                            {/* Header Toggle */}
                            <div
                              className="faq-card-header"
                              onClick={() => handleToggleExpand(faq.id)}
                            >
                              <div className="faq-card-title-row">
                                <h4 className="faq-question">
                                  {idx + 1}. {faq.question}
                                </h4>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                                  <span className="chip chip-score">
                                    Score: {result.score.toFixed(4)}
                                  </span>
                                  {isExpanded ? <ChevronUp size={16} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />}
                                </div>
                              </div>

                              <div className="faq-badges-row">
                                <span className="chip chip-teal">
                                  {result.match_type}
                                </span>
                                {faq.is_verified ? (
                                  <span className="chip chip-green">
                                    <CheckCircle size={10} /> Verified
                                  </span>
                                ) : (
                                  <span className="chip chip-slate">
                                    <HelpCircle size={10} /> Unverified
                                  </span>
                                )}
                                {faq.topic && (
                                  <span className="chip chip-blue">{faq.topic}</span>
                                )}
                                {faq.category && (
                                  <span className="chip chip-teal">{faq.category}</span>
                                )}
                                {faq.subtopic && (
                                  <span className="chip chip-amber">{faq.subtopic}</span>
                                )}
                                {faq.document_publish_date && (
                                  <span className="chip chip-cyan">
                                    Published: {new Date(faq.document_publish_date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                                  </span>
                                )}
                              </div>
                            </div>

                            {/* Collapsed/Expanded Body */}
                            {isExpanded && (
                              <div className="faq-card-body">
                                <div className="faq-answer-container">
                                  {faq.answer}
                                </div>

                                {/* Historical Answers Accordion Section */}
                                {faq.historical_answers && faq.historical_answers.length > 0 && (
                                  <div className="historical-answers-section">
                                    <label className="checkbox-group" style={{ fontWeight: 600 }}>
                                      <input
                                        type="checkbox"
                                        checked={showHistorical[faq.id] || false}
                                        onChange={(e) => setShowHistorical(prev => ({ ...prev, [faq.id]: e.target.checked }))}
                                      />
                                      Show Compliance revisions history ({faq.historical_answers.length})
                                    </label>

                                    {showHistorical[faq.id] && (
                                      <div className="historical-list">
                                        {faq.historical_answers.map((hist, hIdx) => (
                                          <div key={hist.id} className="historical-item" style={{ marginTop: hIdx > 0 ? '0.75rem' : 0 }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                                              <strong>Version {faq.historical_answers.length - hIdx} • Published: {new Date(hist.document_publish_date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}</strong>
                                              {hist.source_url && (
                                                <a href={hist.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-teal)', fontWeight: 'bold' }}>
                                                  PDF Link
                                                </a>
                                              )}
                                            </div>
                                            <div className="faq-answer-container" style={{ fontSize: '12px', background: '#F8FAFC', padding: '0.5rem 0.75rem', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                                              {hist.answer}
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Checklists & Related FAQs Accordion */}
                                {detail ? (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                    {detail.checklists && detail.checklists.length > 0 ? (
                                      <div className="details-accordion">
                                        <div className="details-header">
                                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                            <CheckSquare size={13} style={{ color: 'var(--accent-teal)' }} />
                                            Implementation Checklists ({detail.checklists.length})
                                          </span>
                                        </div>
                                        <div className="details-content">
                                          <div className="checklist-list">
                                            {detail.checklists.map(c => (
                                              <div key={c.id} className="checklist-item-card">
                                                <div className="checklist-title-row">
                                                  <span>{c.title}</span>
                                                  <span className="chip" style={{ fontSize: '8px', padding: '1px 4px', background: c.priority === 'high' ? '#FEF2F2' : '#F3F6FA', color: c.priority === 'high' ? '#DC2626' : 'var(--text-secondary)' }}>
                                                    {c.priority} priority
                                                  </span>
                                                </div>
                                                {c.description && <p className="checklist-desc">{c.description}</p>}
                                                {c.items && c.items.length > 0 && (
                                                  <ul className="checklist-sub-items">
                                                    {c.items.map(item => (
                                                      <li key={item.id}>
                                                        {item.title}
                                                      </li>
                                                    ))}
                                                  </ul>
                                                )}
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      </div>
                                    ) : (
                                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px', padding: '0.15rem' }}>
                                        <Info size={11} /> No audit checklists generated
                                      </div>
                                    )}

                                    {detail.related_faq_ids && detail.related_faq_ids.length > 0 && (
                                      <div className="details-accordion">
                                        <div className="details-header">
                                          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                            <Layers size={13} style={{ color: 'var(--accent-teal)' }} />
                                            Linked Obligations ({detail.related_faq_ids.length})
                                          </span>
                                        </div>
                                        <div className="details-content" style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                          {detail.related_faq_ids.map(id => (
                                            <div key={id} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '11px', color: 'var(--text-secondary)' }}>
                                              <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--accent-teal)' }}></span>
                                              <span>Obligation ID: {id}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', padding: '0.25rem' }}>
                                    Loading audit checklists...
                                  </div>
                                )}

                                {/* Footer meta info */}
                                <div className="faq-footer-meta">
                                  <span className="meta-item">
                                    Source Document: {faq.source_url ? (
                                      <a href={faq.source_url} target="_blank" rel="noreferrer">SEBI Circular link</a>
                                    ) : 'Official SEBI Site'}
                                  </span>
                                  <span className="meta-item">
                                    Ingested by: <span style={{ fontFamily: 'var(--font-mono)' }}>{faq.extracted_by || 'system'}</span>
                                  </span>
                                  <span className="meta-item">
                                    Entity ID: <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>{faq.id}</span>
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="empty-state" style={{ background: '#FFFFFF', border: '1px solid #D8E0EA' }}>
                      <Database size={36} style={{ color: 'var(--text-muted)' }} />
                      <h3>No Obligations Retrieved</h3>
                      <p>
                        Select your parameters in the search controls panel and enter a query to display matching SEBI compliance obligations.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'extract' ? (
            /* 2. INGESTION TAB (Regulatory Monitor) */
            !adminToken ? (
              renderLoginView()
            ) : (
              <div className="extract-container">
              <div className="stats-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="stat-card">
                  <h3 className="section-title" style={{ margin: 0 }}>Spreadsheet Extraction</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '0.25rem' }}>
                    Crawls official circular URLs from spreadsheets to feed the parsing and ingestion pipelines.
                  </p>
                </div>
                <div className="stat-card">
                  <h3 className="section-title" style={{ margin: 0, color: 'var(--accent-teal)' }}>Ingest Validation</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '0.25rem' }}>
                    Processes uploads, filters duplicates, records version archives, and updates vector spaces.
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
                {/* Card 1: Bulk Ingestion */}
                <div className="extract-column-card">
                  <h3 className="section-title">Ingestion Pipeline</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '1rem', minHeight: '36px' }}>
                    Upload a spreadsheet containing SEBI PDF links to scrape and load them as compliance obligations.
                  </p>

                  <div className="upload-card" onClick={() => document.getElementById('excel-file-input').click()}>
                    <input
                      type="file"
                      id="excel-file-input"
                      accept=".xlsx, .xls, .csv"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSelectedFile(e.target.files[0])
                          setExtractResult(null)
                          setExtractError(null)
                        }
                      }}
                    />
                    <FileText size={24} className="upload-icon" />
                    <span style={{ fontWeight: 600, fontSize: '12px' }}>Choose spreadsheet file</span>

                    {selectedFile && (
                      <div className="file-info" onClick={(e) => e.stopPropagation()}>
                        <FileText size={12} />
                        <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedFile.name}</span>
                      </div>
                    )}
                  </div>

                  <button
                    className="btn-upload"
                    style={{ width: '100%', marginTop: '1rem' }}
                    onClick={handleExcelExtract}
                    disabled={!selectedFile || extractLoading || !serverOnline}
                  >
                    {extractLoading ? 'Ingesting...' : 'Start Ingest Pipeline'}
                  </button>

                  {extractError && (
                    <div style={{ color: 'var(--chip-critical-fg)', fontSize: '11px', display: 'flex', gap: '0.4rem', background: 'var(--chip-critical-bg)', padding: '0.6rem', borderRadius: '6px', border: '1px solid var(--chip-critical-br)', marginTop: '0.75rem' }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>{extractError}</span>
                    </div>
                  )}
                </div>

                {/* Card 2: Metadata Enrichment */}
                <div className="extract-column-card">
                  <h3 className="section-title">Metadata Enrichment</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '1rem', minHeight: '36px' }}>
                    Upload a spreadsheet to update categories, topics, subtopics, and publication dates for active records.
                  </p>

                  <div className="upload-card" onClick={() => document.getElementById('meta-file-input').click()}>
                    <input
                      type="file"
                      id="meta-file-input"
                      accept=".xlsx, .xls, .csv"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSelectedMetaFile(e.target.files[0])
                          setMetaResult(null)
                          setMetaError(null)
                        }
                      }}
                    />
                    <FileText size={24} className="upload-icon" />
                    <span style={{ fontWeight: 600, fontSize: '12px' }}>Choose metadata file</span>

                    {selectedMetaFile && (
                      <div className="file-info" onClick={(e) => e.stopPropagation()}>
                        <FileText size={12} />
                        <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedMetaFile.name}</span>
                      </div>
                    )}
                  </div>

                  <button
                    className="btn-upload"
                    style={{ width: '100%', marginTop: '1rem' }}
                    onClick={handleMetadataUpdate}
                    disabled={!selectedMetaFile || metaLoading || !serverOnline}
                  >
                    {metaLoading ? 'Enriching...' : 'Start Enrichment'}
                  </button>

                  {metaError && (
                    <div style={{ color: 'var(--chip-critical-fg)', fontSize: '11px', display: 'flex', gap: '0.4rem', background: 'var(--chip-critical-bg)', padding: '0.6rem', borderRadius: '6px', border: '1px solid var(--chip-critical-br)', marginTop: '0.75rem' }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>{metaError}</span>
                    </div>
                  )}
                </div>

                {/* Card 3: Single PDF Ingestion */}
                <div className="extract-column-card">
                  <h3 className="section-title">Single PDF Ingestion</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '0.75rem', minHeight: '36px' }}>
                    Extract obligations from a single PDF document by upload or remote link, and append custom tags.
                  </p>

                  {/* Toggle source */}
                  <div style={{ display: 'flex', gap: '0.25rem', background: '#F3F6FA', padding: '0.15rem', borderRadius: '5px', border: '1px solid var(--border-color)', marginBottom: '0.75rem' }}>
                    <button
                      type="button"
                      onClick={() => { setPdfSourceType('file'); setPdfResult(null); setPdfError(null); }}
                      style={{ flex: 1, padding: '0.3rem', border: 'none', background: pdfSourceType === 'file' ? '#FFFFFF' : 'transparent', color: pdfSourceType === 'file' ? 'var(--accent-teal)' : 'var(--text-muted)', fontSize: '11px', fontWeight: 600, borderRadius: '4px', cursor: 'pointer' }}
                    >
                      Local File
                    </button>
                    <button
                      type="button"
                      onClick={() => { setPdfSourceType('link'); setPdfResult(null); setPdfError(null); }}
                      style={{ flex: 1, padding: '0.3rem', border: 'none', background: pdfSourceType === 'link' ? '#FFFFFF' : 'transparent', color: pdfSourceType === 'link' ? 'var(--accent-teal)' : 'var(--text-muted)', fontSize: '11px', fontWeight: 600, borderRadius: '4px', cursor: 'pointer' }}
                    >
                      Remote Link
                    </button>
                  </div>

                  {pdfSourceType === 'file' ? (
                    <div className="upload-card" style={{ padding: '1.25rem' }} onClick={() => document.getElementById('pdf-file-input').click()}>
                      <input
                        type="file"
                        id="pdf-file-input"
                        accept=".pdf"
                        style={{ display: 'none' }}
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            setSelectedPdfFile(e.target.files[0])
                            setPdfResult(null)
                            setPdfError(null)
                          }
                        }}
                      />
                      <FileText size={20} className="upload-icon" />
                      <span style={{ fontWeight: 600, fontSize: '11px' }}>Choose PDF document</span>

                      {selectedPdfFile && (
                        <div className="file-info" onClick={(e) => e.stopPropagation()}>
                          <FileText size={10} />
                          <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedPdfFile.name}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                      <input
                        type="url"
                        placeholder="https://sebi.gov.in/circular.pdf"
                        value={pdfUrlInput}
                        onChange={(e) => { setPdfUrlInput(e.target.value); setPdfResult(null); setPdfError(null); }}
                        className="form-input"
                        style={{ fontSize: '12px' }}
                      />
                    </div>
                  )}

                  {/* Metadata fields */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <div className="form-group">
                      <label style={{ fontSize: '10px' }}>Category</label>
                      <input
                        type="text"
                        placeholder="e.g. LODR"
                        value={pdfCategory}
                        onChange={(e) => setPdfCategory(e.target.value)}
                        className="form-input"
                        style={{ fontSize: '11px', padding: '0.35rem 0.5rem' }}
                      />
                    </div>
                    <div className="form-group">
                      <label style={{ fontSize: '10px' }}>Topic</label>
                      <input
                        type="text"
                        placeholder="e.g. Audit"
                        value={pdfTopic}
                        onChange={(e) => setPdfTopic(e.target.value)}
                        className="form-input"
                        style={{ fontSize: '11px', padding: '0.35rem 0.5rem' }}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.25rem' }}>
                    <div className="form-group">
                      <label style={{ fontSize: '10px' }}>Subtopic</label>
                      <input
                        type="text"
                        placeholder="e.g. Revisions"
                        value={pdfSubtopic}
                        onChange={(e) => setPdfSubtopic(e.target.value)}
                        className="form-input"
                        style={{ fontSize: '11px', padding: '0.35rem 0.5rem' }}
                      />
                    </div>
                    <div className="form-group">
                      <label style={{ fontSize: '10px' }}>Publish Date</label>
                      <input
                        type="date"
                        value={pdfDate}
                        onChange={(e) => setPdfDate(e.target.value)}
                        className="form-input"
                        style={{ fontSize: '11px', padding: '0.35rem 0.5rem', color: 'var(--text-primary)' }}
                      />
                    </div>
                  </div>

                  <button
                    className="btn-upload"
                    style={{ width: '100%', marginTop: '0.75rem' }}
                    onClick={handlePdfExtract}
                    disabled={(pdfSourceType === 'file' ? !selectedPdfFile : !pdfUrlInput) || pdfLoading || !serverOnline}
                  >
                    {pdfLoading ? 'Extracting...' : 'Extract & Ingest PDF'}
                  </button>

                  {pdfError && (
                    <div style={{ color: 'var(--chip-critical-fg)', fontSize: '11px', display: 'flex', gap: '0.4rem', background: 'var(--chip-critical-bg)', padding: '0.6rem', borderRadius: '6px', border: '1px solid var(--chip-critical-br)', marginTop: '0.75rem' }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>{pdfError}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Progress spinners */}
              {extractLoading && (
                <div className="spinner-container" style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '2rem' }}>
                  <div className="spinner"></div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '0.5rem' }}>Crawling PDF sheets, running regex engines, generating vector metrics, and database writing...</p>
                </div>
              )}

              {metaLoading && (
                <div className="spinner-container" style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '2rem' }}>
                  <div className="spinner"></div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '0.5rem' }}>Comparing spreadsheet rows and updating matching URL records...</p>
                </div>
              )}

              {pdfLoading && (
                <div className="spinner-container" style={{ background: '#FFFFFF', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '2rem' }}>
                  <div className="spinner"></div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '0.5rem' }}>Downloading PDF, executing line-split parsing heuristics, and updating database...</p>
                </div>
              )}

              {/* Ingestion results */}
              {extractResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div className="extract-stats">
                    <div className="extract-stat-card">
                      <span className="stat-label">Spreadsheet URLs</span>
                      <span className="extract-stat-val cyan">{extractResult.pdf_links_found?.length || 0}</span>
                    </div>
                    <div className="extract-stat-card">
                      <span className="stat-label">Ingested FAQs</span>
                      <span className="extract-stat-val emerald">{extractResult.total_ingested_faqs || 0}</span>
                    </div>
                    <div className="extract-stat-card">
                      <span className="stat-label">Failed / Duplicate</span>
                      <span className="extract-stat-val rose">{extractResult.total_failed_faqs || 0}</span>
                    </div>
                  </div>

                  {extractResult.extracted_faqs && extractResult.extracted_faqs.length > 0 && (
                    <div className="extract-results-card">
                      <h3 className="section-title" style={{ border: 'none' }}>Extraction Pipeline Summary</h3>
                      <div className="extract-table-container">
                        <table className="extract-table">
                          <thead>
                            <tr>
                              <th>URL Source</th>
                              <th>Status</th>
                              <th>Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {extractResult.extracted_faqs.map((item, idx) => (
                              <tr key={idx}>
                                <td className="extract-url-cell">
                                  <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-teal)' }}>
                                    {item.source_url}
                                  </a>
                                </td>
                                <td>
                                  <span className={`extract-status-badge ${item.status}`}>
                                    {item.status}
                                  </span>
                                </td>
                                <td style={{ color: item.status === 'failed' ? '#DC2626' : 'var(--text-secondary)' }}>
                                  {item.status === 'failed' ? item.error : `Q: "${item.question?.substring(0, 75)}..."`}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Enrichment results */}
              {metaResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div className="extract-stats">
                    <div className="extract-stat-card">
                      <span className="stat-label">Spreadsheet Rows</span>
                      <span className="extract-stat-val cyan">{metaResult.total_rows_processed || 0}</span>
                    </div>
                    <div className="extract-stat-card">
                      <span className="stat-label">Updated FAQs</span>
                      <span className="extract-stat-val emerald">{metaResult.total_updated_faqs || 0}</span>
                    </div>
                    <div className="extract-stat-card">
                      <span className="stat-label">Skipped Links</span>
                      <span className="extract-stat-val rose">
                        {metaResult.details?.filter(d => d.status === 'skipped').length || 0}
                      </span>
                    </div>
                  </div>

                  {metaResult.details && metaResult.details.length > 0 && (
                    <div className="extract-results-card">
                      <h3 className="section-title" style={{ border: 'none' }}>Metadata Update Logs</h3>
                      <div className="extract-table-container">
                        <table className="extract-table">
                          <thead>
                            <tr>
                              <th>PDF URL Source</th>
                              <th>Status</th>
                              <th>Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {metaResult.details.map((item, idx) => (
                              <tr key={idx}>
                                <td className="extract-url-cell">
                                  <a href={item.pdf_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-teal)' }}>
                                    {item.pdf_url}
                                  </a>
                                </td>
                                <td>
                                  <span className={`extract-status-badge ${item.status === 'skipped' ? 'failed' : 'success'}`}>
                                    {item.status}
                                  </span>
                                </td>
                                <td style={{ color: item.status === 'skipped' ? 'var(--text-muted)' : '#16A34A' }}>
                                  {item.status === 'skipped' ? item.reason : `Modified ${item.updated_count} FAQ schema headers`}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Single PDF results */}
              {pdfResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div className="extract-stats">
                    <div className="extract-stat-card">
                      <span className="stat-label">Ingested FAQs</span>
                      <span className="extract-stat-val emerald">{pdfResult.total_ingested_faqs || 0}</span>
                    </div>
                    <div className="extract-stat-card">
                      <span className="stat-label">Skipped / Failed</span>
                      <span className="extract-stat-val rose">{pdfResult.total_failed_faqs || 0}</span>
                    </div>
                  </div>

                  {pdfResult.extracted_faqs && pdfResult.extracted_faqs.length > 0 && (
                    <div className="extract-results-card">
                      <h3 className="section-title" style={{ border: 'none' }}>PDF Extraction Log</h3>
                      <div className="extract-table-container">
                        <table className="extract-table">
                          <thead>
                            <tr>
                              <th>Status</th>
                              <th>Extracted Question</th>
                              <th>Answer Snippet / Failure Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pdfResult.extracted_faqs.map((item, idx) => (
                              <tr key={idx}>
                                <td>
                                  <span className={`extract-status-badge ${item.status}`}>
                                    {item.status}
                                  </span>
                                </td>
                                <td style={{ fontWeight: 600, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {item.question}
                                </td>
                                <td style={{ color: item.status === 'failed' ? '#DC2626' : 'var(--text-secondary)', maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {item.status === 'failed' ? item.error : item.answer}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            )
          ) : activeTab === 'analytics' ? (
            /* 3. AUDIT LOGS / ANALYTICS TAB */
            !adminToken ? (
              renderLoginView()
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {analytics ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                  {/* Grid */}
                  <div className="stats-grid">
                    <div className="stat-card">
                      <span className="stat-label">Telemetry Searches</span>
                      <span className="stat-val">{analytics.total_searches}</span>
                      <span className="stat-sub">Query volume (past 7 days)</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Average Response Time</span>
                      <span className="stat-val">{analytics.average_response_time_ms.toFixed(1)} ms</span>
                      <span className="stat-sub">Vector similarity + SQL map</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Semantic Searches</span>
                      <span className="stat-val">{analytics.search_type_distribution?.semantic || 0}</span>
                      <span className="stat-sub">Vector similarity searches</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Hybrid/Combined</span>
                      <span className="stat-val">{analytics.search_type_distribution?.combined || 0}</span>
                      <span className="stat-sub">Weighted keyword+vector searches</span>
                    </div>
                  </div>

                  {/* Split logs */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
                    {/* Common queries */}
                    <div className="stat-card">
                      <h3 className="section-title">Most Searched Queries</h3>
                      {analytics.most_common_queries && analytics.most_common_queries.length > 0 ? (
                        <div className="logs-list" style={{ marginTop: '0.5rem' }}>
                          {analytics.most_common_queries.map(([q, count], index) => (
                            <div key={index} className="log-item">
                              <span className="log-query">"{q}"</span>
                              <span className="chip chip-score">{count} hits</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '0.5rem' }}>No search queries logged yet.</p>
                      )}
                    </div>

                    {/* Types */}
                    <div className="stat-card">
                      <h3 className="section-title">Query Types Telemetry</h3>
                      <div className="logs-list" style={{ marginTop: '0.5rem' }}>
                        <div className="log-item">
                          <span>Semantic (Vector) Retrieval</span>
                          <span className="log-type">{analytics.search_type_distribution?.semantic || 0}</span>
                        </div>
                        <div className="log-item">
                          <span>Hybrid (Combined) Retrieval</span>
                          <span className="log-type">{analytics.search_type_distribution?.combined || 0}</span>
                        </div>
                        <div className="log-item">
                          <span>Full-Text Keyword Retrieval</span>
                          <span className="log-type">{analytics.search_type_distribution?.fulltext || 0}</span>
                        </div>
                        <div className="log-item">
                          <span>Metadata Filter-Only Retrieval</span>
                          <span className="log-type">{analytics.search_type_distribution?.filter || 0}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="empty-state" style={{ background: '#FFFFFF', border: '1px solid #D8E0EA' }}>
                  <Clock size={36} style={{ color: 'var(--text-muted)' }} />
                  <h3>No Telemetry Logs</h3>
                  <p>Execute search queries in the Query Hub to populate search log analytics.</p>
                </div>
              )}
            </div>
            )
          ) : (
            /* 4. MOCK CORE SERVICE PLACEHOLDER VIEW */
            renderPlaceholder(activeTab)
          )}
        </main>
      </div>
    </div>
  )
}

export default App
