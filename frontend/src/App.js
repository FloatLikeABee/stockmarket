import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Paper,
  Grid,
  Button,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Card,
  CardContent,
  Pagination,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  Menu as MenuIcon,
  Refresh as RefreshIcon,
  BarChart as ChartIcon,
  Storage as DatabaseIcon,
  TrendingUp as StockIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import axios from 'axios';
import {
  BarChart as RechartsBarChart,
  Bar,
  LineChart as RechartsLineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

// Create a dark theme with purple and green
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#9c27b0', // Purple
    },
    secondary: {
      main: '#4caf50', // Green
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
    text: {
      primary: '#ffffff',
      secondary: '#b3b3b3',
    },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#1a1a2e',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#252526',
          color: '#ffffff',
          padding: '16px',
          borderRadius: '8px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
        },
      },
    },
  },
});

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [currentView, setCurrentView] = useState('overview'); // 'overview', 'charts', 'browser', 'stocks', 'historical', 'grid-trading'
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonData, setJsonData] = useState(null);
  const [manualCrawlStatus, setManualCrawlStatus] = useState(null);
  
  // Pagination state for stocks
  const [stocksPage, setStocksPage] = useState(1);
  const [stocksPerPage, setStocksPerPage] = useState(50);
  const [stocksData, setStocksData] = useState([]);
  const [stocksTotal, setStocksTotal] = useState(0);
  const [stocksLoading, setStocksLoading] = useState(false);
  const [stocksOrderBy, setStocksOrderBy] = useState('symbol');
  const [stocksOrderDir, setStocksOrderDir] = useState('ASC');
  const [stocksFilter, setStocksFilter] = useState('');
  
  // Historical data state
  const [historicalSymbol, setHistoricalSymbol] = useState('');
  const [historicalStartDate, setHistoricalStartDate] = useState('');
  const [historicalEndDate, setHistoricalEndDate] = useState('');
  const [historicalPeriod, setHistoricalPeriod] = useState('daily');
  const [historicalAdjust, setHistoricalAdjust] = useState('qfq');
  const [historicalData, setHistoricalData] = useState([]);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [historicalError, setHistoricalError] = useState(null);
  
  // Grid Trading state
  const [gridStrategies, setGridStrategies] = useState([]);
  const [gridStrategiesLoading, setGridStrategiesLoading] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [gridStrategyForm, setGridStrategyForm] = useState({
    symbol: '',
    name: '',
    grid_type: 'ARITHMETIC',
    lower_price: '',
    upper_price: '',
    grid_count: 10,
    capital: '',
    order_size_type: 'FIXED',
    order_size: 100,
    take_profit: '',
    stop_loss: '',
    paper_trading: true
  });
  const [currentPrice, setCurrentPrice] = useState(null);

  // Update the API base URL to use the new port
  const API_BASE_URL = 'http://localhost:9878';

  // Handle opening modal with record details
  const handleOpenModal = (record) => {
    setSelectedRecord(record);
    setModalOpen(true);
  };

  // Handle closing modal
  const handleCloseModal = () => {
    setModalOpen(false);
    setSelectedRecord(null);
  };

  // Handle opening JSON modal
  const handleOpenJsonModal = (record) => {
    setJsonData(record);
    setJsonModalOpen(true);
  };

  // Handle closing JSON modal
  const handleCloseJsonModal = () => {
    setJsonModalOpen(false);
    setJsonData(null);
  };

  // Transform raw/incomplete data into structured format
  const transformRawData = (rawText, siteData) => {
    if (!rawText || typeof rawText !== 'string') {
      return null;
    }
    
    const transformed = {
      stocks: [],
      indices: [],
      marketOverview: '',
      topGainers: [],
      topLosers: [],
    };
    
    try {
      // Try to extract stock codes with names and prices
      // Pattern: stock code, name, price, change, change_percent
      const stockPattern = /(\d{6})[:\s,]+([\u4e00-\u9fa5A-Za-z0-9]+)[:\s,]+(\d+\.?\d*)[:\s,]*([+-]?\d+\.?\d*)?[:\s,]*([+-]?\d+\.?\d*%)?/g;
      const stockMatches = [...rawText.matchAll(stockPattern)];
      stockMatches.forEach(match => {
        if (match[1] && match[3]) { // Must have code and price
          transformed.stocks.push({
            symbol: match[1],
            name: match[2] || 'N/A',
            price: match[3] || 'N/A',
            change: match[4] || 'N/A',
            change_percent: match[5] || 'N/A',
            volume: 'N/A'
          });
        }
      });
      
      // Try to extract indices (common Chinese stock indices with values)
      const indexPattern = /(上证指数|深证成指|创业板指|沪深300|中证500|上证50|科创50|北证50)[:\s]+(\d+\.?\d*)[\s(]*([+-]?\d+\.?\d*%)?/g;
      const indexMatches = [...rawText.matchAll(indexPattern)];
      indexMatches.forEach(match => {
        transformed.indices.push({
          name: match[1],
          value: match[2] || 'N/A',
          change: 'N/A',
          change_percent: match[3] || 'N/A'
        });
      });
      
      // Try to extract percentage changes (for gainers/losers)
      const gainerPattern = /([\u4e00-\u9fa5A-Za-z0-9]+)[:\s]+([+-]?\d+\.?\d*%)/g;
      const gainerMatches = [...rawText.matchAll(gainerPattern)];
      gainerMatches.forEach(match => {
        const percent = parseFloat(match[2]);
        if (!isNaN(percent)) {
          if (percent > 0) {
            transformed.topGainers.push(match[1] + ' ' + match[2]);
          } else if (percent < 0) {
            transformed.topLosers.push(match[1] + ' ' + match[2]);
          }
        }
      });
      
      // Try to extract market overview (look for summary sentences)
      const overviewPatterns = [
        /(?:市场|行情|今日|今日市场|大盘)[^。]{20,150}。/g,
        /(?:上涨|下跌|涨幅|跌幅)[^。]{10,100}。/g
      ];
      
      for (const pattern of overviewPatterns) {
        const matches = rawText.match(pattern);
        if (matches && matches.length > 0) {
          transformed.marketOverview = matches[0];
          break;
        }
      }
      
      // Only return if we extracted something useful
      if (transformed.stocks.length > 0 || transformed.indices.length > 0 || 
          transformed.marketOverview || transformed.topGainers.length > 0 || 
          transformed.topLosers.length > 0) {
        return transformed;
      }
    } catch (e) {
      console.warn('Error transforming raw data:', e);
    }
    
    return null;
  };

  // Extract stock symbols and data from a record
  const extractStockData = (record) => {
    const stocks = [];

    try {
      if (!record || !record.data) {
        return stocks;
      }

      Object.keys(record.data).forEach(site => {
        try {
          const siteData = record.data[site];

          // Skip if siteData is null, undefined, or not an object
          if (!siteData || typeof siteData !== 'object') {
            return;
          }

          // Check if ai_processed_data exists and is not null
          if (!siteData.ai_processed_data) {
            return;
          }

          const processedData = siteData.ai_processed_data;

          // Skip if processedData is a string or null
          if (typeof processedData === 'string' || processedData === null) {
            return;
          }

          // Get stocks array, handle different formats
          let stocksArray = [];
          if (Array.isArray(processedData)) {
            stocksArray = processedData;
          } else if (processedData.stocks && Array.isArray(processedData.stocks)) {
            stocksArray = processedData.stocks;
          }

          // Process each stock
          stocksArray.forEach(stock => {
            try {
              if (!stock || typeof stock !== 'object') {
                return;
              }

              // Validate stock has required fields and is not placeholder data
              if (stock.symbol &&
                  stock.symbol !== '未提供公司名称' &&
                  stock.symbol !== 'AAPL' &&
                  stock.symbol !== 'GOOGL' &&
                  stock.symbol !== 'stock symbol' &&
                  stock.name !== 'company name' &&
                  stock.name !== 'N/A') {
                stocks.push({
                  symbol: stock.symbol,
                  name: stock.name || 'N/A',
                  price: stock.price || 'N/A',
                  change: stock.change || 'N/A',
                  change_percent: stock.change_percent || 'N/A',
                  volume: stock.volume || 'N/A',
                  site: site
                });
              }
            } catch (stockError) {
              // Skip individual stock errors
              console.warn(`Error processing stock:`, stockError);
            }
          });
        } catch (siteError) {
          // Skip individual site errors
          console.warn(`Error processing site ${site}:`, siteError);
        }
      });
    } catch (error) {
      console.error('Error in extractStockData:', error);
    }

    return stocks;
  };

  // Prepare chart data from latest record
  const prepareChartData = () => {
    if (!data || data.length === 0) return null;

    try {
      const latestRecord = data[0];
      if (!latestRecord) return null;

      const stocks = extractStockData(latestRecord);
      if (!stocks || stocks.length === 0) return null;

      // Filter valid stocks with numeric prices
      const validStocks = stocks.filter(stock => {
        if (!stock || !stock.price) return false;
        const price = parseFloat(stock.price);
        return !isNaN(price) && price > 0 && stock.price !== '-' && stock.price !== 'N/A';
      });

      // Prepare data for bar chart (top indices by price)
      const priceData = validStocks
        .map(stock => ({
          name: stock.name && stock.name.length > 15 ? stock.name.substring(0, 15) + '...' : (stock.name || 'N/A'),
          price: parseFloat(stock.price),
          symbol: stock.symbol
        }))
        .filter(item => !isNaN(item.price))
        .sort((a, b) => b.price - a.price)
        .slice(0, 20);  // Increased from 10 to 20

      // Prepare data for change percentage chart
      const changeData = validStocks
        .filter(stock => stock.change_percent && stock.change_percent !== '-' && stock.change_percent !== 'N/A')
        .map(stock => {
          const changePercent = parseFloat(String(stock.change_percent).replace('%', ''));
          return {
            name: stock.name && stock.name.length > 15 ? stock.name.substring(0, 15) + '...' : (stock.name || 'N/A'),
            change: isNaN(changePercent) ? 0 : changePercent,
            symbol: stock.symbol
          };
        })
        .filter(item => !isNaN(item.change))
        .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
        .slice(0, 20);  // Increased from 10 to 20

      // Prepare pie chart data (market distribution by index type)
      const marketTypes = {};
      validStocks.forEach(stock => {
        if (stock.name && stock.name.includes('指数')) {
          const type = stock.name.includes('上证') ? '上证' :
                       stock.name.includes('深证') ? '深证' :
                       stock.name.includes('创业板') ? '创业板' :
                       stock.name.includes('北证') ? '北证' :
                       stock.name.includes('香港') || stock.name.includes('恒生') ? '港股' :
                       stock.name.includes('台湾') ? '台股' : '其他';
          marketTypes[type] = (marketTypes[type] || 0) + 1;
        }
      });

      const pieData = Object.keys(marketTypes).map(key => ({
        name: key,
        value: marketTypes[key]
      }));

      return {
        priceData: priceData || [],
        changeData: changeData || [],
        pieData: pieData || [],
        totalStocks: validStocks.length || 0
      };
    } catch (error) {
      console.error('Error preparing chart data:', error);
      return null;
    }
  };

  // Fetch latest stock data
  const fetchLatestData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/data/latest?limit=10`);
      setData(response.data.records || []);
    } catch (error) {
      console.error('获取数据时出错:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('获取统计信息时出错:', error);
    }
  };

  // Fetch rate limit status
  const fetchRateLimitStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/rate_limit_status`);
      setManualCrawlStatus(response.data.manual_crawl);
    } catch (error) {
      console.error('获取速率限制状态时出错:', error);
    }
  };
  
  // Fetch stocks with pagination
  const fetchStocks = async () => {
    setStocksLoading(true);
    try {
      const params = new URLSearchParams({
        page: stocksPage.toString(),
        per_page: stocksPerPage.toString(),
        order_by: stocksOrderBy,
        order_dir: stocksOrderDir
      });
      if (stocksFilter) {
        params.append('symbol', stocksFilter);
      }
      const response = await axios.get(`${API_BASE_URL}/stocks?${params}`);
      setStocksData(response.data.stocks || []);
      setStocksTotal(response.data.pagination?.total || 0);
    } catch (error) {
      console.error('获取股票数据时出错:', error);
    } finally {
      setStocksLoading(false);
    }
  };
  
  // Update stocks when pagination changes
  useEffect(() => {
    if (currentView === 'stocks') {
      fetchStocks();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stocksPage, stocksPerPage, stocksOrderBy, stocksOrderDir, stocksFilter]);
  
  // Fetch grid strategies when view changes
  useEffect(() => {
    if (currentView === 'grid-trading') {
      fetchGridStrategies();
    }
  }, [currentView]);
  
  // Fetch historical data
  const fetchHistoricalData = async () => {
    if (!historicalSymbol || !historicalStartDate || !historicalEndDate) {
      setHistoricalError('请填写股票代码、开始日期和结束日期');
      return;
    }
    
    setHistoricalLoading(true);
    setHistoricalError(null);
    try {
      const params = new URLSearchParams({
        symbol: historicalSymbol,
        start_date: historicalStartDate.replace(/-/g, ''),
        end_date: historicalEndDate.replace(/-/g, ''),
        period: historicalPeriod,
        adjust: historicalAdjust
      });
      const response = await axios.get(`${API_BASE_URL}/historical?${params}`);
      setHistoricalData(response.data.data || []);
      if (response.data.count === 0) {
        setHistoricalError('未找到历史数据，请检查股票代码和日期范围');
      }
    } catch (error) {
      console.error('获取历史数据时出错:', error);
      setHistoricalError(error.response?.data?.detail || '获取历史数据失败');
      setHistoricalData([]);
    } finally {
      setHistoricalLoading(false);
    }
  };
  
  // Grid Trading functions
  const fetchGridStrategies = async () => {
    setGridStrategiesLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/grid-strategies`);
      setGridStrategies(response.data.strategies || []);
    } catch (error) {
      console.error('获取网格策略时出错:', error);
    } finally {
      setGridStrategiesLoading(false);
    }
  };
  
  const fetchCurrentPrice = async (symbol) => {
    if (!symbol) return;
    try {
      const stocks = await axios.get(`${API_BASE_URL}/stocks?symbol=${symbol}&per_page=1`);
      if (stocks.data.stocks && stocks.data.stocks.length > 0) {
        const price = parseFloat(stocks.data.stocks[0].price);
        setCurrentPrice(price);
        if (!gridStrategyForm.lower_price) {
          setGridStrategyForm(prev => ({ ...prev, lower_price: (price * 0.95).toFixed(2) }));
        }
        if (!gridStrategyForm.upper_price) {
          setGridStrategyForm(prev => ({ ...prev, upper_price: (price * 1.05).toFixed(2) }));
        }
      }
    } catch (error) {
      console.error('获取当前价格时出错:', error);
    }
  };
  
  const createGridStrategy = async () => {
    try {
      const strategyData = {
        ...gridStrategyForm,
        lower_price: parseFloat(gridStrategyForm.lower_price),
        upper_price: parseFloat(gridStrategyForm.upper_price),
        grid_count: parseInt(gridStrategyForm.grid_count),
        capital: parseFloat(gridStrategyForm.capital),
        order_size: parseFloat(gridStrategyForm.order_size),
        take_profit: gridStrategyForm.take_profit ? parseFloat(gridStrategyForm.take_profit) : null,
        stop_loss: gridStrategyForm.stop_loss ? parseFloat(gridStrategyForm.stop_loss) : null
      };
      
      await axios.post(`${API_BASE_URL}/grid-strategies`, strategyData);
      alert('策略创建成功！');
      setGridStrategyForm({
        symbol: '',
        name: '',
        grid_type: 'ARITHMETIC',
        lower_price: '',
        upper_price: '',
        grid_count: 10,
        capital: '',
        order_size_type: 'FIXED',
        order_size: 100,
        take_profit: '',
        stop_loss: '',
        paper_trading: true
      });
      fetchGridStrategies();
    } catch (error) {
      console.error('创建策略时出错:', error);
      alert('创建策略失败: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  const startStrategy = async (strategyId) => {
    try {
      await axios.post(`${API_BASE_URL}/grid-strategies/${strategyId}/start`);
      alert('策略已启动');
      fetchGridStrategies();
    } catch (error) {
      alert('启动策略失败: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  const stopStrategy = async (strategyId) => {
    if (window.confirm('确定要停止策略吗？')) {
      try {
        await axios.post(`${API_BASE_URL}/grid-strategies/${strategyId}/stop`);
        alert('策略已停止');
        fetchGridStrategies();
      } catch (error) {
        alert('停止策略失败: ' + (error.response?.data?.detail || error.message));
      }
    }
  };
  
  const pauseStrategy = async (strategyId) => {
    try {
      await axios.post(`${API_BASE_URL}/grid-strategies/${strategyId}/pause`);
      alert('策略已暂停');
      fetchGridStrategies();
    } catch (error) {
      alert('暂停策略失败: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  const resumeStrategy = async (strategyId) => {
    try {
      await axios.post(`${API_BASE_URL}/grid-strategies/${strategyId}/resume`);
      alert('策略已恢复');
      fetchGridStrategies();
    } catch (error) {
      alert('恢复策略失败: ' + (error.response?.data?.detail || error.message));
    }
  };
  
  const fetchStrategyDetails = async (strategyId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/grid-strategies/${strategyId}`);
      setSelectedStrategy(response.data);
    } catch (error) {
      console.error('获取策略详情时出错:', error);
    }
  };

  // Trigger crawl
  const triggerCrawl = async () => {
    // Check rate limit first
    if (manualCrawlStatus && !manualCrawlStatus.can_crawl) {
      const remaining = Math.ceil(manualCrawlStatus.remaining_wait_time);
      const minutes = Math.floor(remaining / 60);
      const seconds = remaining % 60;
      alert(`请等待 ${minutes} 分 ${seconds} 秒后再试 (手动爬取间隔: 10分钟)`);
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/crawl`, {
        sites: null, // Crawl all sites
        category: "manual"
      });
      // Refresh rate limit status
      fetchRateLimitStatus();
      // Refresh data after crawl - wait longer for background task to complete
      setTimeout(() => {
        fetchLatestData();
        fetchStats();
        fetchRateLimitStatus();
      }, 10000); // Wait 10 seconds for crawl to complete
    } catch (error) {
      console.error('触发爬取时出错:', error);
      if (error.response && error.response.status === 429) {
        alert(error.response.data.detail || '请求过于频繁，请稍后再试');
        fetchRateLimitStatus(); // Refresh status
      }
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatestData();
    fetchStats();
    fetchRateLimitStatus();
    
    // Update rate limit status every 5 seconds to show countdown
    // Reduced from 1 second to reduce API load
    const interval = setInterval(() => {
      fetchRateLimitStatus();
    }, 5000); // Poll every 5 seconds instead of every second
    
    return () => clearInterval(interval);
  }, []);

  const drawerWidth = 240;
  const drawer = (
    <div>
      <Toolbar />
      <List>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'overview'}
            onClick={() => setCurrentView('overview')}
          >
            <ListItemIcon>
              <StockIcon style={{ color: currentView === 'overview' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="股票概览" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'charts'}
            onClick={() => setCurrentView('charts')}
          >
            <ListItemIcon>
              <ChartIcon style={{ color: currentView === 'charts' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="图表" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'browser'}
            onClick={() => setCurrentView('browser')}
          >
            <ListItemIcon>
              <DatabaseIcon style={{ color: currentView === 'browser' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="数据浏览器" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'stocks'}
            onClick={() => {
              setCurrentView('stocks');
              fetchStocks();
            }}
          >
            <ListItemIcon>
              <StockIcon style={{ color: currentView === 'stocks' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="股票列表" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'historical'}
            onClick={() => setCurrentView('historical')}
          >
            <ListItemIcon>
              <ChartIcon style={{ color: currentView === 'historical' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="历史数据" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            selected={currentView === 'grid-trading'}
            onClick={() => setCurrentView('grid-trading')}
          >
            <ListItemIcon>
              <StockIcon style={{ color: currentView === 'grid-trading' ? '#bb86fc' : 'inherit' }} />
            </ListItemIcon>
            <ListItemText primary="网格交易" />
          </ListItemButton>
        </ListItem>
      </List>
    </div>
  );

  return (
    <ThemeProvider theme={theme}>
      <div style={{ display: 'flex' }}>
        <AppBar position="fixed">
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={() => setMobileOpen(!mobileOpen)}
              sx={{ mr: 2, display: { sm: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
              中国股票市场数据
            </Typography>
            <Button 
              color="inherit" 
              onClick={triggerCrawl} 
              startIcon={<RefreshIcon />}
              disabled={loading || (manualCrawlStatus && !manualCrawlStatus.can_crawl)}
            >
              {loading ? '爬取中...' : 
               (manualCrawlStatus && !manualCrawlStatus.can_crawl) ? 
                 `等待中 (${Math.ceil(manualCrawlStatus.remaining_wait_time / 60)}分)` : 
                 '立即爬取'}
            </Button>
          </Toolbar>
        </AppBar>

        <Box
          component="nav"
          sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
          style={{ paddingTop: '64px' }}
        >
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            sx={{
              display: { xs: 'block', sm: 'none' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
          >
            {drawer}
          </Drawer>
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: 'none', sm: 'block' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
            open
          >
            {drawer}
          </Drawer>
        </Box>

        <Box
          component="main"
          sx={{ flexGrow: 1, p: 3, width: { sm: `calc(100% - ${drawerWidth}px)` } }}
          style={{ paddingTop: '64px' }}
        >
          <Toolbar />
          <Container maxWidth="xl">
            {/* Stock Overview View */}
            {currentView === 'overview' && (
              <Grid container spacing={3}>
                {/* Stats Cards */}
                {stats && (
                  <Grid item xs={12} md={12}>
                    <Paper>
                      <Grid container spacing={2}>
                        <Grid item xs={4}>
                          <Typography variant="h6" color="textSecondary">记录总数</Typography>
                          <Typography variant="h4">{stats.total_records || 0}</Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="h6" color="textSecondary">跟踪网站</Typography>
                          <Typography variant="h4">{Object.keys(stats.sites || {}).length}</Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="h6" color="textSecondary">最后更新</Typography>
                          <Typography variant="h4">
                            {stats.latest_update ? new Date(stats.latest_update).toLocaleTimeString() : 'N/A'}
                          </Typography>
                        </Grid>
                      </Grid>
                    </Paper>
                  </Grid>
                )}

                {/* Latest Data */}
                <Grid item xs={12}>
                  <Paper>
                    <Typography variant="h5" gutterBottom>
                      最新股票数据
                    </Typography>
                    {loading ? (
                      <Box display="flex" justifyContent="center" p={4}>
                        <CircularProgress />
                      </Box>
                    ) : (
                      <TableContainer>
                        <Table>
                          <TableHead>
                            <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '15%' }}>日期</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '8%' }}>类别</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '20%' }}>数据源</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '10%' }}>股票数量</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '32%' }}>市场概况</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold', width: '15%' }}>操作</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {data.length === 0 ? (
                              <TableRow>
                                <TableCell colSpan={6} align="center">
                                  <Typography>暂无数据</Typography>
                                </TableCell>
                              </TableRow>
                            ) : (
                              data.map((record, index) => {
                                const sites = record.metadata?.sites_crawled || [];
                                const category = record.metadata?.category || 'unknown';
                                const timestamp = record.timestamp || 'N/A';
                                const stocks = extractStockData(record);

                                // Get market overview from first site
                                let marketOverview = 'N/A';
                                if (record.data) {
                                  const firstSite = Object.keys(record.data)[0];
                                  if (firstSite && record.data[firstSite]?.ai_processed_data?.market_overview) {
                                    const overview = record.data[firstSite].ai_processed_data.market_overview;
                                    // Show full overview, but truncate if too long for table display
                                    marketOverview = overview.length > 150 ? overview.substring(0, 150) + '...' : overview;
                                  }
                                }

                                return (
                                  <TableRow
                                    key={index}
                                    hover
                                    style={{
                                      cursor: 'pointer',
                                      backgroundColor: index % 2 === 0 ? '#2a2a3e' : '#252526'
                                    }}
                                    onClick={() => handleOpenModal(record)}
                                  >
                                    <TableCell style={{ width: '15%' }}>
                                      <Typography variant="body2">
                                        {new Date(timestamp).toLocaleDateString()}
                                      </Typography>
                                      <Typography variant="caption" color="textSecondary">
                                        {new Date(timestamp).toLocaleTimeString()}
                                      </Typography>
                                    </TableCell>
                                    <TableCell style={{ width: '8%' }}>
                                      <Chip
                                        label={category}
                                        size="small"
                                        color={category === 'manual' ? 'secondary' : 'primary'}
                                      />
                                    </TableCell>
                                    <TableCell style={{ width: '20%' }}>
                                      <Typography variant="body2">
                                        {sites.slice(0, 2).join(', ')}
                                        {sites.length > 2 && ` +${sites.length - 2}`}
                                      </Typography>
                                    </TableCell>
                                    <TableCell style={{ width: '10%' }}>
                                      <Typography variant="body2" style={{ color: '#4caf50' }}>
                                        {stocks.length} 支股票
                                      </Typography>
                                    </TableCell>
                                    <TableCell style={{ width: '32%' }}>
                                      <Typography
                                        variant="body2"
                                        color="textSecondary"
                                        style={{
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          display: '-webkit-box',
                                          WebkitLineClamp: 2,
                                          WebkitBoxOrient: 'vertical'
                                        }}
                                      >
                                        {marketOverview}
                                      </Typography>
                                    </TableCell>
                                    <TableCell style={{ width: '15%' }}>
                                      <Button
                                        variant="outlined"
                                        size="small"
                                        style={{ color: '#bb86fc', borderColor: '#bb86fc' }}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleOpenModal(record);
                                        }}
                                      >
                                        查看详情
                                      </Button>
                                    </TableCell>
                                  </TableRow>
                                );
                              })
                            )}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    )}
                  </Paper>
                </Grid>
              </Grid>
            )}

            {/* Charts View */}
            {currentView === 'charts' && (() => {
              const chartData = prepareChartData();
              const COLORS = ['#bb86fc', '#4caf50', '#ff9800', '#f44336', '#2196f3', '#9c27b0', '#00bcd4', '#ffeb3b'];

              if (!chartData) {
                return (
                  <Grid container spacing={3}>
                    <Grid item xs={12}>
                      <Paper>
                        <Typography variant="h5" gutterBottom>
                          图表分析
                        </Typography>
                        <Box p={4} textAlign="center">
                          <CircularProgress />
                          <Typography variant="body2" color="textSecondary" style={{ marginTop: '16px' }}>
                            加载数据中...
                          </Typography>
                        </Box>
                      </Paper>
                    </Grid>
                  </Grid>
                );
              }

              return (
                <Grid container spacing={3}>
                  {/* Header */}
                  <Grid item xs={12}>
                    <Paper style={{ padding: '16px', backgroundColor: '#1a1a2e' }}>
                      <Typography variant="h5" style={{ color: '#bb86fc' }}>
                        图表分析 - 最新数据
                      </Typography>
                      <Typography variant="body2" color="textSecondary" style={{ marginTop: '8px' }}>
                        基于最新爬取的 {chartData.totalStocks} 支股票/指数数据
                      </Typography>
                    </Paper>
                  </Grid>

                  {/* Top Indices by Price */}
                  <Grid item xs={12} lg={6}>
                    <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                      <Typography variant="h6" style={{ color: '#4caf50', marginBottom: '16px' }}>
                        主要指数价格排行
                      </Typography>
                      <ResponsiveContainer width="100%" height={300}>
                        <RechartsBarChart data={chartData.priceData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                          <XAxis
                            dataKey="name"
                            angle={-45}
                            textAnchor="end"
                            height={100}
                            tick={{ fill: '#aaa', fontSize: 12 }}
                          />
                          <YAxis tick={{ fill: '#aaa' }} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #bb86fc' }}
                            labelStyle={{ color: '#bb86fc' }}
                          />
                          <Bar dataKey="price" fill="#4caf50" />
                        </RechartsBarChart>
                      </ResponsiveContainer>
                    </Paper>
                  </Grid>

                  {/* Top Movers by Change Percentage */}
                  <Grid item xs={12} lg={6}>
                    <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                      <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                        涨跌幅排行
                      </Typography>
                      <ResponsiveContainer width="100%" height={300}>
                        <RechartsBarChart data={chartData.changeData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                          <XAxis
                            dataKey="name"
                            angle={-45}
                            textAnchor="end"
                            height={100}
                            tick={{ fill: '#aaa', fontSize: 12 }}
                          />
                          <YAxis tick={{ fill: '#aaa' }} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #bb86fc' }}
                            labelStyle={{ color: '#bb86fc' }}
                          />
                          <Bar dataKey="change" fill="#bb86fc">
                            {chartData.changeData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.change >= 0 ? '#4caf50' : '#f44336'} />
                            ))}
                          </Bar>
                        </RechartsBarChart>
                      </ResponsiveContainer>
                    </Paper>
                  </Grid>

                  {/* Market Distribution Pie Chart */}
                  {chartData.pieData.length > 0 && (
                    <Grid item xs={12} lg={6}>
                      <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                        <Typography variant="h6" style={{ color: '#ff9800', marginBottom: '16px' }}>
                          市场分布
                        </Typography>
                        <ResponsiveContainer width="100%" height={300}>
                          <PieChart>
                            <Pie
                              data={chartData.pieData}
                              cx="50%"
                              cy="50%"
                              labelLine={false}
                              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                              outerRadius={80}
                              fill="#8884d8"
                              dataKey="value"
                            >
                              {chartData.pieData.map((_entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #bb86fc' }}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </Paper>
                    </Grid>
                  )}

                  {/* Stock Summary Cards */}
                  <Grid item xs={12} lg={6}>
                    <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                      <Typography variant="h6" style={{ color: '#2196f3', marginBottom: '16px' }}>
                        市场概况
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Card style={{ backgroundColor: '#1a1a2e', textAlign: 'center', padding: '16px' }}>
                            <CardContent>
                              <Typography variant="h4" style={{ color: '#4caf50' }}>
                                {chartData.changeData.filter(s => s.change > 0).length}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                上涨
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                        <Grid item xs={6}>
                          <Card style={{ backgroundColor: '#1a1a2e', textAlign: 'center', padding: '16px' }}>
                            <CardContent>
                              <Typography variant="h4" style={{ color: '#f44336' }}>
                                {chartData.changeData.filter(s => s.change < 0).length}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                下跌
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                        <Grid item xs={12}>
                          <Card style={{ backgroundColor: '#1a1a2e', textAlign: 'center', padding: '16px' }}>
                            <CardContent>
                              <Typography variant="h4" style={{ color: '#bb86fc' }}>
                                {chartData.totalStocks}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                总股票/指数数
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      </Grid>
                    </Paper>
                  </Grid>

                  {/* Historical Data List */}
                  <Grid item xs={12}>
                    <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                      <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                        历史数据记录
                      </Typography>
                      <TableContainer>
                        <Table size="small">
                          <TableHead>
                            <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>日期时间</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>类别</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>数据源</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>股票数</TableCell>
                              <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>操作</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {data.slice(1).map((record, index) => {
                              const sites = record.metadata?.sites_crawled || [];
                              const category = record.metadata?.category || 'unknown';
                              const timestamp = record.timestamp || 'N/A';
                              const stocks = extractStockData(record);

                              return (
                                <TableRow
                                  key={index}
                                  hover
                                  style={{
                                    cursor: 'pointer',
                                    backgroundColor: index % 2 === 0 ? '#252526' : '#1e1e1e'
                                  }}
                                  onClick={() => handleOpenModal(record)}
                                >
                                  <TableCell>
                                    <Typography variant="body2">
                                      {new Date(timestamp).toLocaleString()}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      label={category}
                                      size="small"
                                      color={category === 'manual' ? 'secondary' : 'primary'}
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Typography variant="body2">
                                      {sites.slice(0, 2).join(', ')}
                                      {sites.length > 2 && ` +${sites.length - 2}`}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    <Typography variant="body2" style={{ color: '#4caf50' }}>
                                      {stocks.length}
                                    </Typography>
                                  </TableCell>
                                  <TableCell>
                                    <Button
                                      variant="outlined"
                                      size="small"
                                      style={{ color: '#bb86fc', borderColor: '#bb86fc' }}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleOpenModal(record);
                                      }}
                                    >
                                      查看
                                    </Button>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </TableContainer>
                      {data.length <= 1 && (
                        <Box p={2} textAlign="center">
                          <Typography variant="body2" color="textSecondary">
                            暂无历史数据
                          </Typography>
                        </Box>
                      )}
                    </Paper>
                  </Grid>
                </Grid>
              );
            })()}

            {/* Data Browser View */}
            {currentView === 'browser' && (
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Paper>
                    <Typography variant="h5" gutterBottom>
                      数据浏览器
                    </Typography>
                    <Box p={2}>
                      <Typography variant="body1" gutterBottom>
                        浏览所有爬取的数据文件
                      </Typography>
                      {loading ? (
                        <Box display="flex" justifyContent="center" p={4}>
                          <CircularProgress />
                        </Box>
                      ) : (
                        <div>
                          {data.length === 0 ? (
                            <Typography>暂无数据</Typography>
                          ) : (
                            data.map((record, index) => {
                              const sites = record.metadata?.sites_crawled || [];
                              const category = record.metadata?.category || 'unknown';
                              const timestamp = record.timestamp || 'N/A';
                              const filepath = record.filepath || 'N/A';

                              // Extract just the filename from the path
                              const filename = filepath.split('/').pop() || filepath;

                              return (
                                <Paper
                                  key={index}
                                  style={{
                                    padding: '12px',
                                    marginBottom: '12px',
                                    backgroundColor: '#2a2a3e',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                    border: '1px solid transparent'
                                  }}
                                  onMouseEnter={(e) => {
                                    e.currentTarget.style.backgroundColor = '#3a3a4e';
                                    e.currentTarget.style.borderColor = '#bb86fc';
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.backgroundColor = '#2a2a3e';
                                    e.currentTarget.style.borderColor = 'transparent';
                                  }}
                                  onClick={() => handleOpenJsonModal(record)}
                                >
                                  <Grid container spacing={2} alignItems="center">
                                    <Grid item xs={12} md={5}>
                                      <Typography variant="body2" color="textSecondary">
                                        文件名:
                                      </Typography>
                                      <Typography
                                        variant="body1"
                                        style={{
                                          color: '#4caf50',
                                          fontFamily: 'monospace',
                                          fontSize: '0.9rem',
                                          wordBreak: 'break-word'
                                        }}
                                      >
                                        {filename}
                                      </Typography>
                                    </Grid>
                                    <Grid item xs={12} md={4}>
                                      <Typography variant="body2" color="textSecondary">
                                        数据源:
                                      </Typography>
                                      <Typography variant="body1" style={{ fontSize: '0.9rem' }}>
                                        {sites.slice(0, 3).join(', ')}
                                        {sites.length > 3 && ` +${sites.length - 3}`}
                                      </Typography>
                                    </Grid>
                                    <Grid item xs={12} md={3}>
                                      <Typography variant="body2" color="textSecondary">
                                        类别:
                                      </Typography>
                                      <Chip
                                        label={category}
                                        size="small"
                                        color={category === 'manual' ? 'secondary' : 'primary'}
                                        style={{ marginTop: '4px' }}
                                      />
                                    </Grid>
                                    <Grid item xs={12}>
                                      <Typography variant="body2" color="textSecondary">
                                        📅 {new Date(timestamp).toLocaleString('zh-CN', {
                                          year: 'numeric',
                                          month: '2-digit',
                                          day: '2-digit',
                                          hour: '2-digit',
                                          minute: '2-digit'
                                        })}
                                      </Typography>
                                    </Grid>
                                  </Grid>
                                </Paper>
                              );
                            })
                          )}
                        </div>
                      )}
                    </Box>
                  </Paper>
                </Grid>
              </Grid>
            )}

            {/* Stocks View with Pagination */}
            {currentView === 'stocks' && (
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Paper>
                    <Typography variant="h5" gutterBottom style={{ color: '#bb86fc' }}>
                      股票列表 ({stocksTotal})
                    </Typography>
                    
                    {/* Filters and Controls */}
                    <Box display="flex" gap={2} mb={2} flexWrap="wrap">
                      <TextField
                        label="搜索股票代码"
                        variant="outlined"
                        size="small"
                        value={stocksFilter}
                        onChange={(e) => {
                          setStocksFilter(e.target.value);
                          setStocksPage(1);
                        }}
                        style={{ minWidth: '200px' }}
                      />
                      <FormControl size="small" style={{ minWidth: '150px' }}>
                        <InputLabel>排序字段</InputLabel>
                        <Select
                          value={stocksOrderBy}
                          label="排序字段"
                          onChange={(e) => {
                            setStocksOrderBy(e.target.value);
                            setStocksPage(1);
                          }}
                        >
                          <MenuItem value="symbol">代码</MenuItem>
                          <MenuItem value="name">名称</MenuItem>
                          <MenuItem value="price">价格</MenuItem>
                          <MenuItem value="change_percent">涨跌幅</MenuItem>
                          <MenuItem value="volume">成交量</MenuItem>
                        </Select>
                      </FormControl>
                      <FormControl size="small" style={{ minWidth: '120px' }}>
                        <InputLabel>排序方向</InputLabel>
                        <Select
                          value={stocksOrderDir}
                          label="排序方向"
                          onChange={(e) => {
                            setStocksOrderDir(e.target.value);
                            setStocksPage(1);
                          }}
                        >
                          <MenuItem value="ASC">升序</MenuItem>
                          <MenuItem value="DESC">降序</MenuItem>
                        </Select>
                      </FormControl>
                      <FormControl size="small" style={{ minWidth: '120px' }}>
                        <InputLabel>每页数量</InputLabel>
                        <Select
                          value={stocksPerPage}
                          label="每页数量"
                          onChange={(e) => {
                            setStocksPerPage(e.target.value);
                            setStocksPage(1);
                          }}
                        >
                          <MenuItem value={25}>25</MenuItem>
                          <MenuItem value={50}>50</MenuItem>
                          <MenuItem value={100}>100</MenuItem>
                          <MenuItem value={200}>200</MenuItem>
                        </Select>
                      </FormControl>
                    </Box>
                    
                    {stocksLoading ? (
                      <Box display="flex" justifyContent="center" p={4}>
                        <CircularProgress />
                      </Box>
                    ) : (
                      <>
                        <TableContainer>
                          <Table>
                            <TableHead>
                              <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>代码</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>名称</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>价格</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>涨跌</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>涨跌幅</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>成交量</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>成交额</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>最高</TableCell>
                                <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>最低</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {stocksData.length === 0 ? (
                                <TableRow>
                                  <TableCell colSpan={9} align="center">
                                    <Typography>暂无数据</Typography>
                                  </TableCell>
                                </TableRow>
                              ) : (
                                stocksData.map((stock, index) => (
                                  <TableRow
                                    key={index}
                                    hover
                                    style={{
                                      backgroundColor: index % 2 === 0 ? '#2a2a3e' : '#252526'
                                    }}
                                  >
                                    <TableCell style={{ color: '#4caf50', fontFamily: 'monospace' }}>
                                      {stock.symbol}
                                    </TableCell>
                                    <TableCell>{stock.name || 'N/A'}</TableCell>
                                    <TableCell>{stock.price || 'N/A'}</TableCell>
                                    <TableCell
                                      style={{
                                        color: stock.change && (typeof stock.change === 'string' ? stock.change.includes('-') : parseFloat(stock.change) < 0) ? '#f44336' : '#4caf50'
                                      }}
                                    >
                                      {stock.change || 'N/A'}
                                    </TableCell>
                                    <TableCell
                                      style={{
                                        color: stock.change_percent && (typeof stock.change_percent === 'string' ? stock.change_percent.includes('-') : parseFloat(stock.change_percent) < 0) ? '#f44336' : '#4caf50'
                                      }}
                                    >
                                      {stock.change_percent || 'N/A'}
                                    </TableCell>
                                    <TableCell>{stock.volume || 'N/A'}</TableCell>
                                    <TableCell>{stock.turnover || 'N/A'}</TableCell>
                                    <TableCell>{stock.high || 'N/A'}</TableCell>
                                    <TableCell>{stock.low || 'N/A'}</TableCell>
                                  </TableRow>
                                ))
                              )}
                            </TableBody>
                          </Table>
                        </TableContainer>
                        
                        {/* Pagination */}
                        <Box display="flex" justifyContent="center" mt={3}>
                          <Pagination
                            count={Math.ceil(stocksTotal / stocksPerPage)}
                            page={stocksPage}
                            onChange={(event, value) => setStocksPage(value)}
                            color="primary"
                            size="large"
                          />
                        </Box>
                      </>
                    )}
                  </Paper>
                </Grid>
              </Grid>
            )}

            {/* Historical Data View */}
            {currentView === 'historical' && (
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Paper style={{ padding: '24px', backgroundColor: '#2a2a3e' }}>
                    <Typography variant="h5" gutterBottom style={{ color: '#bb86fc' }}>
                      股票历史数据查询
                    </Typography>
                    
                    <Box display="flex" flexDirection="column" gap={2} mb={3}>
                      <Grid container spacing={2}>
                        <Grid item xs={12} sm={6} md={3}>
                          <TextField
                            fullWidth
                            label="股票代码"
                            value={historicalSymbol}
                            onChange={(e) => setHistoricalSymbol(e.target.value)}
                            placeholder="例如: 000001"
                            variant="outlined"
                            size="small"
                            style={{ backgroundColor: '#1a1a2e' }}
                            InputLabelProps={{ style: { color: '#aaa' } }}
                            inputProps={{ style: { color: '#fff' } }}
                          />
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                          <TextField
                            fullWidth
                            label="开始日期"
                            type="date"
                            value={historicalStartDate}
                            onChange={(e) => setHistoricalStartDate(e.target.value)}
                            InputLabelProps={{ shrink: true, style: { color: '#aaa' } }}
                            inputProps={{ style: { color: '#fff' } }}
                            variant="outlined"
                            size="small"
                            style={{ backgroundColor: '#1a1a2e' }}
                          />
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                          <TextField
                            fullWidth
                            label="结束日期"
                            type="date"
                            value={historicalEndDate}
                            onChange={(e) => setHistoricalEndDate(e.target.value)}
                            InputLabelProps={{ shrink: true, style: { color: '#aaa' } }}
                            inputProps={{ style: { color: '#fff' } }}
                            variant="outlined"
                            size="small"
                            style={{ backgroundColor: '#1a1a2e' }}
                          />
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                          <FormControl fullWidth size="small" style={{ backgroundColor: '#1a1a2e' }}>
                            <InputLabel style={{ color: '#aaa' }}>周期</InputLabel>
                            <Select
                              value={historicalPeriod}
                              label="周期"
                              onChange={(e) => setHistoricalPeriod(e.target.value)}
                              style={{ color: '#fff' }}
                            >
                              <MenuItem value="daily">日线</MenuItem>
                              <MenuItem value="weekly">周线</MenuItem>
                              <MenuItem value="monthly">月线</MenuItem>
                            </Select>
                          </FormControl>
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                          <FormControl fullWidth size="small" style={{ backgroundColor: '#1a1a2e' }}>
                            <InputLabel style={{ color: '#aaa' }}>复权类型</InputLabel>
                            <Select
                              value={historicalAdjust}
                              label="复权类型"
                              onChange={(e) => setHistoricalAdjust(e.target.value)}
                              style={{ color: '#fff' }}
                            >
                              <MenuItem value="qfq">前复权</MenuItem>
                              <MenuItem value="hfq">后复权</MenuItem>
                              <MenuItem value="">不复权</MenuItem>
                            </Select>
                          </FormControl>
                        </Grid>
                        <Grid item xs={12} sm={6} md={3}>
                          <Button
                            variant="contained"
                            onClick={fetchHistoricalData}
                            disabled={historicalLoading}
                            style={{ 
                              backgroundColor: '#4caf50', 
                              color: '#fff',
                              height: '40px',
                              minWidth: '120px'
                            }}
                          >
                            {historicalLoading ? '查询中...' : '查询数据'}
                          </Button>
                        </Grid>
                      </Grid>
                    </Box>
                    
                    {historicalError && (
                      <Box mb={2} p={2} style={{ backgroundColor: '#f44336', borderRadius: '4px' }}>
                        <Typography style={{ color: '#fff' }}>{historicalError}</Typography>
                      </Box>
                    )}
                    
                    {historicalLoading ? (
                      <Box display="flex" justifyContent="center" p={4}>
                        <CircularProgress />
                      </Box>
                    ) : historicalData.length > 0 ? (
                      <>
                        <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                          数据图表 ({historicalData.length} 条记录)
                        </Typography>
                        
                        {/* Price Chart */}
                        <Box mb={3}>
                          <Paper style={{ padding: '16px', backgroundColor: '#1a1a2e' }}>
                            <Typography variant="subtitle1" style={{ color: '#4caf50', marginBottom: '12px' }}>
                              价格走势 (开盘/收盘/最高/最低)
                            </Typography>
                            <ResponsiveContainer width="100%" height={400}>
                              <RechartsLineChart data={historicalData.map(item => ({
                                date: item.date,
                                open: item.open,
                                close: item.close,
                                high: item.high,
                                low: item.low
                              }))}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                                <XAxis 
                                  dataKey="date" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={100}
                                  tick={{ fill: '#aaa', fontSize: 10 }}
                                />
                                <YAxis tick={{ fill: '#aaa' }} />
                                <Tooltip 
                                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #4caf50' }}
                                  labelStyle={{ color: '#4caf50' }}
                                />
                                <Legend />
                                <Line type="monotone" dataKey="open" stroke="#4caf50" name="开盘" dot={false} />
                                <Line type="monotone" dataKey="close" stroke="#bb86fc" name="收盘" dot={false} />
                                <Line type="monotone" dataKey="high" stroke="#f44336" name="最高" dot={false} />
                                <Line type="monotone" dataKey="low" stroke="#ff9800" name="最低" dot={false} />
                              </RechartsLineChart>
                            </ResponsiveContainer>
                          </Paper>
                        </Box>
                        
                        {/* Volume Chart */}
                        <Box mb={3}>
                          <Paper style={{ padding: '16px', backgroundColor: '#1a1a2e' }}>
                            <Typography variant="subtitle1" style={{ color: '#4caf50', marginBottom: '12px' }}>
                              成交量
                            </Typography>
                            <ResponsiveContainer width="100%" height={300}>
                              <RechartsBarChart data={historicalData.map(item => ({
                                date: item.date,
                                volume: item.volume
                              }))}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                                <XAxis 
                                  dataKey="date" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={100}
                                  tick={{ fill: '#aaa', fontSize: 10 }}
                                />
                                <YAxis tick={{ fill: '#aaa' }} />
                                <Tooltip 
                                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #4caf50' }}
                                  labelStyle={{ color: '#4caf50' }}
                                />
                                <Bar dataKey="volume" fill="#4caf50" />
                              </RechartsBarChart>
                            </ResponsiveContainer>
                          </Paper>
                        </Box>
                        
                        {/* Data Table */}
                        <Box>
                          <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                            数据表格
                          </Typography>
                          <TableContainer style={{ maxHeight: '600px', overflow: 'auto' }}>
                            <Table size="small" stickyHeader>
                              <TableHead>
                                <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>日期</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>开盘</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>收盘</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>最高</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>最低</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>成交量</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>成交额</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>涨跌幅</TableCell>
                                  <TableCell style={{ color: '#bb86fc', fontWeight: 'bold' }}>换手率</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {historicalData.map((item, index) => (
                                  <TableRow key={index} style={{ backgroundColor: index % 2 === 0 ? '#252526' : '#2a2a3e' }}>
                                    <TableCell style={{ color: '#aaa' }}>{item.date}</TableCell>
                                    <TableCell>{item.open || 'N/A'}</TableCell>
                                    <TableCell>{item.close || 'N/A'}</TableCell>
                                    <TableCell>{item.high || 'N/A'}</TableCell>
                                    <TableCell>{item.low || 'N/A'}</TableCell>
                                    <TableCell>{item.volume ? item.volume.toLocaleString() : 'N/A'}</TableCell>
                                    <TableCell>{item.turnover ? item.turnover.toLocaleString() : 'N/A'}</TableCell>
                                    <TableCell style={{ 
                                      color: item.change_percent && item.change_percent < 0 ? '#f44336' : '#4caf50' 
                                    }}>
                                      {item.change_percent ? `${item.change_percent.toFixed(2)}%` : 'N/A'}
                                    </TableCell>
                                    <TableCell>{item.turnover_rate ? `${item.turnover_rate.toFixed(2)}%` : 'N/A'}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        </Box>
                      </>
                    ) : (
                      <Box p={4} textAlign="center">
                        <Typography variant="body1" color="textSecondary">
                          请输入股票代码和日期范围，然后点击"查询数据"按钮
                        </Typography>
                      </Box>
                    )}
                  </Paper>
                </Grid>
              </Grid>
            )}

            {/* Grid Trading View */}
            {currentView === 'grid-trading' && (
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <Paper style={{ padding: '24px', backgroundColor: '#2a2a3e' }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                      <Typography variant="h5" style={{ color: '#bb86fc' }}>
                        网格交易策略
                      </Typography>
                      <Button
                        variant="contained"
                        onClick={() => setSelectedStrategy(null)}
                        style={{ backgroundColor: '#4caf50', color: '#fff' }}
                      >
                        {selectedStrategy ? '返回列表' : '创建新策略'}
                      </Button>
                    </Box>
                    
                    {!selectedStrategy ? (
                      <>
                        {/* Create Strategy Form */}
                        <Paper style={{ padding: '20px', backgroundColor: '#1a1a2e', marginBottom: '24px' }}>
                          <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                            创建网格交易策略
                          </Typography>
                          <Box display="flex" flexDirection="column" gap={2}>
                            <Grid container spacing={2}>
                              <Grid item xs={12} sm={6}>
                                <TextField
                                  fullWidth
                                  label="股票代码"
                                  value={gridStrategyForm.symbol}
                                  onChange={(e) => {
                                    setGridStrategyForm(prev => ({ ...prev, symbol: e.target.value }));
                                    if (e.target.value.length === 6) {
                                      fetchCurrentPrice(e.target.value);
                                    }
                                  }}
                                  placeholder="例如: 000001"
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                                {currentPrice && (
                                  <Typography variant="caption" style={{ color: '#4caf50', marginTop: '4px' }}>
                                    当前价格: ¥{currentPrice.toFixed(2)}
                                  </Typography>
                                )}
                              </Grid>
                              <Grid item xs={12} sm={6}>
                                <TextField
                                  fullWidth
                                  label="策略名称"
                                  value={gridStrategyForm.name}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, name: e.target.value }))}
                                  placeholder="可选"
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="下限价格"
                                  type="number"
                                  value={gridStrategyForm.lower_price}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, lower_price: e.target.value }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="上限价格"
                                  type="number"
                                  value={gridStrategyForm.upper_price}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, upper_price: e.target.value }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="网格数量"
                                  type="number"
                                  value={gridStrategyForm.grid_count}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, grid_count: parseInt(e.target.value) || 10 }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' }, min: 5, max: 50 }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <FormControl fullWidth size="small" style={{ backgroundColor: '#252526' }}>
                                  <InputLabel style={{ color: '#aaa' }}>网格类型</InputLabel>
                                  <Select
                                    value={gridStrategyForm.grid_type}
                                    label="网格类型"
                                    onChange={(e) => setGridStrategyForm(prev => ({ ...prev, grid_type: e.target.value }))}
                                    style={{ color: '#fff' }}
                                  >
                                    <MenuItem value="ARITHMETIC">算术网格</MenuItem>
                                    <MenuItem value="GEOMETRIC">几何网格</MenuItem>
                                  </Select>
                                </FormControl>
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="投入资金"
                                  type="number"
                                  value={gridStrategyForm.capital}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, capital: e.target.value }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="每单数量"
                                  type="number"
                                  value={gridStrategyForm.order_size}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, order_size: parseFloat(e.target.value) || 100 }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <TextField
                                  fullWidth
                                  label="止损价格 (可选)"
                                  type="number"
                                  value={gridStrategyForm.stop_loss}
                                  onChange={(e) => setGridStrategyForm(prev => ({ ...prev, stop_loss: e.target.value }))}
                                  variant="outlined"
                                  size="small"
                                  style={{ backgroundColor: '#252526' }}
                                  InputLabelProps={{ style: { color: '#aaa' } }}
                                  inputProps={{ style: { color: '#fff' } }}
                                />
                              </Grid>
                              <Grid item xs={12} sm={4}>
                                <FormControl fullWidth size="small" style={{ backgroundColor: '#252526' }}>
                                  <InputLabel style={{ color: '#aaa' }}>交易模式</InputLabel>
                                  <Select
                                    value={gridStrategyForm.paper_trading ? 'paper' : 'real'}
                                    label="交易模式"
                                    onChange={(e) => setGridStrategyForm(prev => ({ ...prev, paper_trading: e.target.value === 'paper' }))}
                                    style={{ color: '#fff' }}
                                  >
                                    <MenuItem value="paper">模拟交易 (推荐)</MenuItem>
                                    <MenuItem value="real" disabled>实盘交易 (未启用)</MenuItem>
                                  </Select>
                                </FormControl>
                              </Grid>
                              <Grid item xs={12}>
                                <Box display="flex" gap={2} alignItems="center">
                                  <Button
                                    variant="contained"
                                    onClick={createGridStrategy}
                                    style={{ backgroundColor: '#4caf50', color: '#fff' }}
                                  >
                                    创建策略
                                  </Button>
                                  <Typography variant="caption" style={{ color: '#f44336' }}>
                                    ⚠️ 风险提示：网格交易存在风险，不保证盈利。建议使用模拟交易模式。
                                  </Typography>
                                </Box>
                              </Grid>
                            </Grid>
                          </Box>
                        </Paper>
                        
                        {/* Active Strategies List */}
                        <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                          策略列表
                        </Typography>
                        {gridStrategiesLoading ? (
                          <Box display="flex" justifyContent="center" p={4}>
                            <CircularProgress />
                          </Box>
                        ) : gridStrategies.length === 0 ? (
                          <Box p={4} textAlign="center">
                            <Typography variant="body1" color="textSecondary">
                              暂无策略，请创建新策略
                            </Typography>
                          </Box>
                        ) : (
                          <TableContainer>
                            <Table>
                              <TableHead>
                                <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                  <TableCell style={{ color: '#bb86fc' }}>ID</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>股票代码</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>策略名称</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>价格区间</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>网格数</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>状态</TableCell>
                                  <TableCell style={{ color: '#bb86fc' }}>操作</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {gridStrategies.map((strategy) => (
                                  <TableRow key={strategy.id} style={{ backgroundColor: '#2a2a3e' }}>
                                    <TableCell>{strategy.id}</TableCell>
                                    <TableCell style={{ fontFamily: 'monospace', color: '#4caf50' }}>
                                      {strategy.symbol}
                                    </TableCell>
                                    <TableCell>{strategy.name || '未命名'}</TableCell>
                                    <TableCell>
                                      ¥{strategy.lower_price} - ¥{strategy.upper_price}
                                    </TableCell>
                                    <TableCell>{strategy.grid_count}</TableCell>
                                    <TableCell>
                                      <Chip
                                        label={strategy.status === 'RUNNING' ? '运行中' : strategy.status === 'PAUSED' ? '已暂停' : '已停止'}
                                        color={strategy.status === 'RUNNING' ? 'success' : strategy.status === 'PAUSED' ? 'warning' : 'default'}
                                        size="small"
                                      />
                                    </TableCell>
                                    <TableCell>
                                      <Box display="flex" gap={1}>
                                        <Button
                                          size="small"
                                          onClick={() => fetchStrategyDetails(strategy.id)}
                                          style={{ color: '#bb86fc' }}
                                        >
                                          详情
                                        </Button>
                                        {strategy.status === 'STOPPED' && (
                                          <Button
                                            size="small"
                                            onClick={() => startStrategy(strategy.id)}
                                            style={{ color: '#4caf50' }}
                                          >
                                            启动
                                          </Button>
                                        )}
                                        {strategy.status === 'RUNNING' && (
                                          <>
                                            <Button
                                              size="small"
                                              onClick={() => pauseStrategy(strategy.id)}
                                              style={{ color: '#ff9800' }}
                                            >
                                              暂停
                                            </Button>
                                            <Button
                                              size="small"
                                              onClick={() => stopStrategy(strategy.id)}
                                              style={{ color: '#f44336' }}
                                            >
                                              停止
                                            </Button>
                                          </>
                                        )}
                                        {strategy.status === 'PAUSED' && (
                                          <>
                                            <Button
                                              size="small"
                                              onClick={() => resumeStrategy(strategy.id)}
                                              style={{ color: '#4caf50' }}
                                            >
                                              恢复
                                            </Button>
                                            <Button
                                              size="small"
                                              onClick={() => stopStrategy(strategy.id)}
                                              style={{ color: '#f44336' }}
                                            >
                                              停止
                                            </Button>
                                          </>
                                        )}
                                      </Box>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        )}
                      </>
                    ) : (
                      /* Strategy Details View */
                      <Grid container spacing={3}>
                        <Grid item xs={12} md={8}>
                          <Paper style={{ padding: '20px', backgroundColor: '#1a1a2e' }}>
                            <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                              策略详情 - {selectedStrategy.strategy?.symbol}
                            </Typography>
                            {selectedStrategy.grid_levels && selectedStrategy.current_price && (
                              <Box>
                                <Typography variant="subtitle1" style={{ color: '#4caf50', marginBottom: '12px' }}>
                                  网格可视化 - 当前价格: ¥{selectedStrategy.current_price.toFixed(2)}
                                </Typography>
                                <ResponsiveContainer width="100%" height={400}>
                                  <RechartsLineChart data={selectedStrategy.grid_levels}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                                    <XAxis 
                                      dataKey="level" 
                                      tick={{ fill: '#aaa' }}
                                      label={{ value: '网格层级', position: 'insideBottom', offset: -5, style: { fill: '#aaa' } }}
                                    />
                                    <YAxis 
                                      tick={{ fill: '#aaa' }}
                                      label={{ value: '价格 (¥)', angle: -90, position: 'insideLeft', style: { fill: '#aaa' } }}
                                    />
                                    <Tooltip 
                                      contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #4caf50' }}
                                      formatter={(value, name) => [`¥${value.toFixed(2)}`, name]}
                                    />
                                    <Line 
                                      type="monotone" 
                                      dataKey="price" 
                                      stroke="#4caf50" 
                                      strokeWidth={2}
                                      name="网格价格"
                                      dot={{ fill: '#4caf50', r: 4 }}
                                    />
                                    {/* Current price line */}
                                    <Line
                                      type="monotone"
                                      data={selectedStrategy.grid_levels.map(() => ({ level: 0, price: selectedStrategy.current_price }))}
                                      stroke="#bb86fc"
                                      strokeWidth={2}
                                      strokeDasharray="5 5"
                                      name="当前价格"
                                      dot={false}
                                    />
                                  </RechartsLineChart>
                                </ResponsiveContainer>
                                
                                {/* Orders Table */}
                                {selectedStrategy.orders && selectedStrategy.orders.length > 0 && (
                                  <Box mt={3}>
                                    <Typography variant="subtitle1" style={{ color: '#bb86fc', marginBottom: '12px' }}>
                                      订单列表
                                    </Typography>
                                    <TableContainer style={{ maxHeight: '300px', overflow: 'auto' }}>
                                      <Table size="small">
                                        <TableHead>
                                          <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                            <TableCell style={{ color: '#bb86fc' }}>网格层级</TableCell>
                                            <TableCell style={{ color: '#bb86fc' }}>方向</TableCell>
                                            <TableCell style={{ color: '#bb86fc' }}>价格</TableCell>
                                            <TableCell style={{ color: '#bb86fc' }}>数量</TableCell>
                                            <TableCell style={{ color: '#bb86fc' }}>状态</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {selectedStrategy.orders.map((order, idx) => (
                                            <TableRow key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#252526' : '#2a2a3e' }}>
                                              <TableCell>{order.grid_level}</TableCell>
                                              <TableCell style={{ color: order.side === 'BUY' ? '#4caf50' : '#f44336' }}>
                                                {order.side === 'BUY' ? '买入' : '卖出'}
                                              </TableCell>
                                              <TableCell>¥{order.price.toFixed(2)}</TableCell>
                                              <TableCell>{order.quantity}</TableCell>
                                              <TableCell>
                                                <Chip
                                                  label={order.status === 'PENDING' ? '待成交' : order.status === 'FILLED' ? '已成交' : '已取消'}
                                                  color={order.status === 'PENDING' ? 'warning' : order.status === 'FILLED' ? 'success' : 'default'}
                                                  size="small"
                                                />
                                              </TableCell>
                                            </TableRow>
                                          ))}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </Box>
                                )}
                              </Box>
                            )}
                          </Paper>
                        </Grid>
                        <Grid item xs={12} md={4}>
                          <Paper style={{ padding: '20px', backgroundColor: '#1a1a2e' }}>
                            <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                              策略统计
                            </Typography>
                            {selectedStrategy.stats && (
                              <Box display="flex" flexDirection="column" gap={2}>
                                <Box>
                                  <Typography variant="body2" color="textSecondary">总交易次数</Typography>
                                  <Typography variant="h6" style={{ color: '#bb86fc' }}>
                                    {selectedStrategy.stats.total_trades || 0}
                                  </Typography>
                                </Box>
                                <Box>
                                  <Typography variant="body2" color="textSecondary">已实现盈亏</Typography>
                                  <Typography variant="h6" style={{ color: selectedStrategy.stats.realized_pnl >= 0 ? '#4caf50' : '#f44336' }}>
                                    ¥{selectedStrategy.stats.realized_pnl?.toFixed(2) || '0.00'}
                                  </Typography>
                                </Box>
                                <Box>
                                  <Typography variant="body2" color="textSecondary">胜率</Typography>
                                  <Typography variant="h6" style={{ color: '#bb86fc' }}>
                                    {selectedStrategy.stats.win_rate?.toFixed(2) || '0.00'}%
                                  </Typography>
                                </Box>
                                <Box>
                                  <Typography variant="body2" color="textSecondary">总手续费</Typography>
                                  <Typography variant="h6" style={{ color: '#bb86fc' }}>
                                    ¥{selectedStrategy.stats.total_fees?.toFixed(2) || '0.00'}
                                  </Typography>
                                </Box>
                              </Box>
                            )}
                          </Paper>
                        </Grid>
                      </Grid>
                    )}
                  </Paper>
                </Grid>
              </Grid>
            )}

          </Container>
        </Box>

        {/* Detail Modal */}
        <Dialog
          open={modalOpen}
          onClose={handleCloseModal}
          maxWidth="lg"
          fullWidth
          PaperProps={{
            style: {
              backgroundColor: '#1e1e1e',
              color: '#ffffff'
            }
          }}
        >
          <DialogTitle style={{ backgroundColor: '#1a1a2e', color: '#bb86fc' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="h5">股票数据详情</Typography>
              <IconButton onClick={handleCloseModal} style={{ color: '#bb86fc' }}>
                <CloseIcon />
              </IconButton>
            </Box>
          </DialogTitle>
          <DialogContent style={{ backgroundColor: '#252526', paddingTop: '20px' }}>
            {selectedRecord && (
              <Grid container spacing={3}>
                {/* Metadata Section */}
                <Grid item xs={12}>
                  <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                    <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '12px' }}>
                      基本信息
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} md={6}>
                        <Typography variant="body2" color="textSecondary">类别</Typography>
                        <Chip
                          label={selectedRecord.metadata?.category || 'unknown'}
                          color={selectedRecord.metadata?.category === 'manual' ? 'secondary' : 'primary'}
                        />
                      </Grid>
                      <Grid item xs={12} md={6}>
                        <Typography variant="body2" color="textSecondary">数据源</Typography>
                        <Typography variant="body1">
                          {selectedRecord.metadata?.sites_crawled?.join(', ') || 'N/A'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Grid>

                {/* Stock Data by Site - AKShare first */}
                {selectedRecord.data && (() => {
                  // Sort sites to display AKShare first
                  const sites = Object.keys(selectedRecord.data);
                  const sortedSites = [...sites].sort((a, b) => {
                    // AKShare always comes first
                    if (a === 'akshare') return -1;
                    if (b === 'akshare') return 1;
                    // Keep original order for others
                    return sites.indexOf(a) - sites.indexOf(b);
                  });
                  
                  return sortedSites.map((site, siteIndex) => {
                    const siteData = selectedRecord.data[site];
                  
                  // Debug: Log the siteData structure
                  console.log(`[Debug] Site: ${site}, siteData:`, siteData);
                  console.log(`[Debug] ai_processed_data:`, siteData?.ai_processed_data);
                  
                  // Hide error sections for web-scraped sites (only show AKShare)
                  const webScrapedSites = ['tonghuashun', 'dongfangcaifu', 'xueqiu', 'tongdaxin', 'caijinglian'];
                  const isWebScrapedSite = webScrapedSites.includes(site);
                  
                  // Handle null or undefined siteData - hide for web-scraped sites
                  if (!siteData) {
                    if (isWebScrapedSite) {
                      return null; // Don't display error for web-scraped sites
                    }
                    return (
                      <Grid item xs={12} key={siteIndex}>
                        <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e', border: '1px solid #ff9800' }}>
                          <Typography variant="h6" style={{ color: '#ff9800', marginBottom: '12px' }}>
                            {site} - 数据为空
                          </Typography>
                          <Typography variant="body2" style={{ color: '#ff9800' }}>
                            该站点的数据为空或未定义
                          </Typography>
                        </Paper>
                      </Grid>
                    );
                  }
                  
                  // Check for errors first - hide for web-scraped sites
                  if (siteData.error) {
                    if (isWebScrapedSite) {
                      return null; // Don't display errors for web-scraped sites
                    }
                    return (
                      <Grid item xs={12} key={siteIndex}>
                        <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e', border: '1px solid #f44336' }}>
                          <Typography variant="h6" style={{ color: '#f44336', marginBottom: '12px' }}>
                            {site} - 错误
                          </Typography>
                          <Typography variant="body2" style={{ color: '#ff9800', marginBottom: '8px' }}>
                            {siteData.error}
                          </Typography>
                          {siteData.raw_data_preview && (
                            <Box mt={2}>
                              <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                                原始数据预览:
                              </Typography>
                              <Paper style={{ padding: '12px', backgroundColor: '#1a1a2e', maxHeight: '200px', overflow: 'auto' }}>
                                <Typography variant="body2" style={{ fontFamily: 'monospace', fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                                  {siteData.raw_data_preview}
                                </Typography>
                              </Paper>
                            </Box>
                          )}
                        </Paper>
                      </Grid>
                    );
                  }
                  
                  // Handle ai_processed_data - it might be a string, object, or raw response object
                  let processedData = siteData?.ai_processed_data;
                  let isRawResponse = false;
                  let rawResponseText = null;
                  let transformedData = null;
                  
                  // First, try to use structured data from deep extraction if available
                  // This helps even when AI processing fails
                  if (!processedData || (typeof processedData === 'object' && Object.keys(processedData).length === 0)) {
                    // Try to extract from raw_data_preview or structured extraction
                    const rawPreview = siteData?.raw_data_preview || '';
                    if (rawPreview) {
                      transformedData = transformRawData(rawPreview, siteData);
                      if (transformedData) {
                        processedData = transformedData;
                      }
                    }
                  }
                  
                  // Extract from followed links data (deep extraction results)
                  if (siteData?.followed_links_data && siteData.followed_links_data.length > 0) {
                    // Extract data from followed links
                    const allTableStocks = [];
                    const allIndices = [];
                    
                    siteData.followed_links_data.forEach(linkData => {
                      if (linkData.tables && linkData.tables.length > 0) {
                        // Transform table data into stocks
                        linkData.tables.forEach(table => {
                          table.forEach((row, idx) => {
                            if (idx > 0 && row.length >= 2) { // Skip header row, need at least 2 columns
                              const rowStr = row.join(' ');
                              const codeMatch = rowStr.match(/\b([0-3][0-9]{5}|6[0-9]{5})\b/);
                              if (codeMatch) {
                                const code = codeMatch[1];
                                allTableStocks.push({
                                  symbol: code,
                                  name: row[1] || row[0] || 'N/A',
                                  price: row[2] || row.find(c => /^\d+\.\d+$/.test(c)) || 'N/A',
                                  change: row.find(c => /^[+-]?\d+\.?\d*$/.test(c)) || 'N/A',
                                  change_percent: row.find(c => /[+-]?\d+\.?\d*%/.test(c)) || 'N/A',
                                  volume: row.find(c => /^\d+[万千]?$/.test(c)) || 'N/A'
                                });
                              }
                            }
                          });
                        });
                      }
                      
                      // Extract indices from link text
                      if (linkData.text) {
                        const indexMatches = linkData.text.matchAll(/(上证指数|深证成指|创业板指|沪深300|中证500|上证50)[:\s]+(\d+\.?\d*)/g);
                        for (const match of indexMatches) {
                          allIndices.push({
                            name: match[1],
                            value: match[2] || 'N/A',
                            change: 'N/A',
                            change_percent: 'N/A'
                          });
                        }
                      }
                    });
                    
                    // Merge extracted data
                    if (allTableStocks.length > 0 || allIndices.length > 0) {
                      if (!processedData || typeof processedData !== 'object') {
                        processedData = {};
                      }
                      if (allTableStocks.length > 0) {
                        processedData.stocks = [...(processedData.stocks || []), ...allTableStocks];
                      }
                      if (allIndices.length > 0) {
                        processedData.indices = [...(processedData.indices || []), ...allIndices];
                      }
                    }
                  }
                  
                  if (typeof processedData === 'string') {
                    // Try to parse if it's a JSON string
                    try {
                      processedData = JSON.parse(processedData);
                    } catch (e) {
                      console.warn(`[Debug] Failed to parse ai_processed_data as JSON for ${site}:`, e);
                      // Try to transform raw text into structured data
                      rawResponseText = processedData;
                      transformedData = transformRawData(processedData, siteData);
                      if (transformedData) {
                        processedData = transformedData; // Use transformed data
                        isRawResponse = false; // We have structured data now
                      } else {
                        isRawResponse = true;
                        processedData = null;
                      }
                    }
                  } else if (processedData && typeof processedData === 'object') {
                    // Check if it's a raw response object (has raw_response field)
                    if (processedData.raw_response !== undefined) {
                      rawResponseText = processedData.raw_response;
                      // Try to transform raw response into structured data
                      transformedData = transformRawData(processedData.raw_response, siteData);
                      if (transformedData) {
                        // Merge transformed data with any existing data
                        processedData = {
                          ...transformedData,
                          ...(processedData.stocks ? { stocks: [...transformedData.stocks, ...processedData.stocks] } : {}),
                          ...(processedData.indices ? { indices: [...transformedData.indices, ...processedData.indices] } : {})
                        };
                        isRawResponse = false; // We have structured data now
                      } else {
                        isRawResponse = true;
                        processedData = null;
                      }
                    }
                  }
                  
                  // Extract data from processedData (use transformed data if available)
                  const stocks = (processedData && !isRawResponse) ? (processedData.stocks || []) : [];
                  const indices = (processedData && !isRawResponse) ? (processedData.indices || []) : [];
                  const topGainers = (processedData && !isRawResponse) ? (processedData.top_gainers || []) : [];
                  const topLosers = (processedData && !isRawResponse) ? (processedData.top_losers || []) : [];
                  const marketOverview = (processedData && !isRawResponse) ? (processedData.market_overview || 'N/A') : 'N/A';
                  const tradingSummary = (processedData && !isRawResponse) ? (processedData.trading_summary || '') : '';
                  const hasError = siteData?.error && !transformedData; // Only show error if we couldn't transform data
                  
                  // Debug: Log extracted data
                  console.log(`[Debug] Extracted for ${site}:`, {
                    stocks: stocks.length,
                    indices: indices.length,
                    topGainers: topGainers.length,
                    topLosers: topLosers.length,
                    hasMarketOverview: !!marketOverview,
                    hasTradingSummary: !!tradingSummary,
                    processedData: processedData
                  });
                  
                  // If it's a web-scraped site with no valid data, don't display it
                  if (isWebScrapedSite && !hasError && processedData && stocks.length === 0 && indices.length === 0 && topGainers.length === 0 && 
                      topLosers.length === 0 && marketOverview === 'N/A' && !tradingSummary) {
                    return null; // Don't display this section
                  }
                  
                  // If it's a web-scraped site with errors, don't display it
                  if (isWebScrapedSite && hasError) {
                    return null; // Don't display error sections for web-scraped sites
                  }

                  return (
                    <Grid item xs={12} key={siteIndex}>
                      <Paper style={{ 
                        padding: '16px', 
                        backgroundColor: site === 'akshare' ? '#2a3e2a' : '#2a2a3e',
                        border: site === 'akshare' ? '2px solid #4caf50' : 'none'
                      }}>
                        <Box display="flex" alignItems="center" gap={1} marginBottom="12px">
                          <Typography variant="h6" style={{ color: site === 'akshare' ? '#4caf50' : '#4caf50' }}>
                            {site === 'akshare' ? 'AKShare (东方财富)' : site} 数据
                          </Typography>
                          {site === 'akshare' && (
                            <Chip 
                              label="优先显示" 
                              size="small" 
                              style={{ 
                                backgroundColor: '#4caf50', 
                                color: '#000',
                                fontWeight: 'bold'
                              }} 
                            />
                          )}
                        </Box>

                        {/* Show warning if AI processing failed but raw data exists */}
                        {(hasError || isRawResponse) && (
                          <Box mb={2} p={1} style={{ backgroundColor: '#ff9800', borderRadius: '4px' }}>
                            <Typography variant="body2" style={{ color: '#000' }}>
                              ⚠️ AI处理失败或未完成，显示原始数据
                            </Typography>
                            {siteData?.error && (
                              <Typography variant="caption" style={{ color: '#000', display: 'block', marginTop: '4px' }}>
                                错误: {siteData.error}
                              </Typography>
                            )}
                            {siteData?.warning && (
                              <Typography variant="caption" style={{ color: '#000', display: 'block', marginTop: '4px' }}>
                                警告: {siteData.warning}
                              </Typography>
                            )}
                          </Box>
                        )}

                        {/* Don't show raw response - we transform it into structured data instead */}
                        {/* Only show if transformation completely failed and we have no data at all */}
                        {isRawResponse && rawResponseText && stocks.length === 0 && indices.length === 0 && 
                         marketOverview === 'N/A' && !tradingSummary && (
                          <Box mb={2}>
                            <Typography variant="body2" color="textSecondary" style={{ fontStyle: 'italic' }}>
                              数据解析中，暂无可用数据
                            </Typography>
                          </Box>
                        )}

                        {/* Market Overview */}
                        {marketOverview && marketOverview !== 'N/A' && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary">市场概况</Typography>
                            <Typography variant="body2" style={{ marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                              {marketOverview}
                            </Typography>
                          </Box>
                        )}

                        {/* Trading Summary */}
                        {tradingSummary && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary">交易总结</Typography>
                            <Typography variant="body2" style={{ marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                              {tradingSummary}
                            </Typography>
                          </Box>
                        )}

                        {/* Market Indices */}
                        {indices.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              市场指数 ({indices.length})
                            </Typography>
                            <TableContainer>
                              <Table size="small">
                                <TableHead>
                                  <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                    <TableCell style={{ color: '#bb86fc' }}>指数名称</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>数值</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>涨跌</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>涨跌幅</TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {indices.map((index, indexIdx) => (
                                    <TableRow key={indexIdx}>
                                      <TableCell>{index.name || 'N/A'}</TableCell>
                                      <TableCell>{index.value || 'N/A'}</TableCell>
                                      <TableCell style={{
                                        color: index.change && String(index.change).includes('-') ? '#f44336' : '#4caf50'
                                      }}>
                                        {index.change || 'N/A'}
                                      </TableCell>
                                      <TableCell style={{
                                        color: index.change_percent && String(index.change_percent).includes('-') ? '#f44336' : '#4caf50'
                                      }}>
                                        {index.change_percent || 'N/A'}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </TableContainer>
                          </Box>
                        )}

                        {/* Top Gainers and Losers - Side by Side with Charts */}
                        {(topGainers.length > 0 || topLosers.length > 0) && (
                          <Box mb={3}>
                            <Typography variant="h6" style={{ color: '#bb86fc', marginBottom: '16px' }}>
                              涨跌幅排行榜
                            </Typography>
                            
                            <Grid container spacing={2}>
                              {/* Top Gainers Table */}
                              {topGainers.length > 0 && (
                                <Grid item xs={12} md={6}>
                                  <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                                    <Typography variant="subtitle1" style={{ color: '#4caf50', marginBottom: '12px', fontWeight: 'bold' }}>
                                      涨幅榜 ({topGainers.length})
                                    </Typography>
                                    <TableContainer style={{ maxHeight: '400px', overflow: 'auto' }}>
                                      <Table size="small">
                                        <TableHead>
                                          <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                            <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>排名</TableCell>
                                            <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>代码</TableCell>
                                            <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>名称</TableCell>
                                            <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>涨跌幅</TableCell>
                                            <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>价格</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {topGainers.slice(0, 20).map((gainer, idx) => {
                                            let symbol = '', name = '', changePercent = '', price = '';
                                            if (typeof gainer === 'string') {
                                              const match = gainer.match(/(\d{6})[^\d]*([+-]?\d+\.?\d*%)/);
                                              if (match) {
                                                symbol = match[1];
                                                changePercent = match[2];
                                              } else {
                                                symbol = gainer.substring(0, 6);
                                                changePercent = gainer.match(/([+-]?\d+\.?\d*%)/)?.[1] || '';
                                              }
                                            } else if (typeof gainer === 'object') {
                                              symbol = gainer.symbol || '';
                                              name = gainer.name || '';
                                              changePercent = gainer.change_percent || gainer.gain || '';
                                              price = gainer.price || '';
                                            }
                                            return (
                                              <TableRow key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#252526' : '#2a2a3e' }}>
                                                <TableCell style={{ color: '#aaa' }}>{idx + 1}</TableCell>
                                                <TableCell style={{ color: '#4caf50', fontFamily: 'monospace' }}>{symbol}</TableCell>
                                                <TableCell>{name || 'N/A'}</TableCell>
                                                <TableCell style={{ color: '#4caf50', fontWeight: 'bold' }}>{changePercent || 'N/A'}</TableCell>
                                                <TableCell>{price || 'N/A'}</TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </Paper>
                                </Grid>
                              )}

                              {/* Top Losers Table */}
                              {topLosers.length > 0 && (
                                <Grid item xs={12} md={6}>
                                  <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                                    <Typography variant="subtitle1" style={{ color: '#f44336', marginBottom: '12px', fontWeight: 'bold' }}>
                                      跌幅榜 ({topLosers.length})
                                    </Typography>
                                    <TableContainer style={{ maxHeight: '400px', overflow: 'auto' }}>
                                      <Table size="small">
                                        <TableHead>
                                          <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                            <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>排名</TableCell>
                                            <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>代码</TableCell>
                                            <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>名称</TableCell>
                                            <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>涨跌幅</TableCell>
                                            <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>价格</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {topLosers.slice(0, 20).map((loser, idx) => {
                                            let symbol = '', name = '', changePercent = '', price = '';
                                            if (typeof loser === 'string') {
                                              const match = loser.match(/(\d{6})[^\d]*([+-]?\d+\.?\d*%)/);
                                              if (match) {
                                                symbol = match[1];
                                                changePercent = match[2];
                                              } else {
                                                symbol = loser.substring(0, 6);
                                                changePercent = loser.match(/([+-]?\d+\.?\d*%)/)?.[1] || '';
                                              }
                                            } else if (typeof loser === 'object') {
                                              symbol = loser.symbol || '';
                                              name = loser.name || '';
                                              changePercent = loser.change_percent || loser.loss || '';
                                              price = loser.price || '';
                                            }
                                            return (
                                              <TableRow key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#252526' : '#2a2a3e' }}>
                                                <TableCell style={{ color: '#aaa' }}>{idx + 1}</TableCell>
                                                <TableCell style={{ color: '#f44336', fontFamily: 'monospace' }}>{symbol}</TableCell>
                                                <TableCell>{name || 'N/A'}</TableCell>
                                                <TableCell style={{ color: '#f44336', fontWeight: 'bold' }}>{changePercent || 'N/A'}</TableCell>
                                                <TableCell>{price || 'N/A'}</TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </Paper>
                                </Grid>
                              )}
                            </Grid>
                            
                            {/* Charts for Gainers and Losers */}
                            <Grid container spacing={2} style={{ marginTop: '16px' }}>
                              {topGainers.length > 0 && (
                                <Grid item xs={12} md={6}>
                                  <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                                    <Typography variant="subtitle1" style={{ color: '#4caf50', marginBottom: '12px', fontWeight: 'bold' }}>
                                      涨幅榜图表
                                    </Typography>
                                    <ResponsiveContainer width="100%" height={300}>
                                      <RechartsBarChart
                                        data={topGainers.slice(0, 10).map((gainer) => {
                                          let symbol = '', changePercent = 0;
                                          if (typeof gainer === 'string') {
                                            const match = gainer.match(/(\d{6})[^\d]*([+-]?\d+\.?\d*%)/);
                                            if (match) {
                                              symbol = match[1];
                                              changePercent = parseFloat(match[2]) || 0;
                                            }
                                          } else if (typeof gainer === 'object') {
                                            symbol = gainer.symbol || '';
                                            changePercent = parseFloat(gainer.change_percent || gainer.gain || '0') || 0;
                                          }
                                          return { name: symbol, value: changePercent };
                                        })}
                                      >
                                        <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                                        <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} tick={{ fill: '#aaa', fontSize: 10 }} />
                                        <YAxis tick={{ fill: '#aaa' }} />
                                        <Tooltip contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #4caf50' }} labelStyle={{ color: '#4caf50' }} formatter={(value) => `${value}%`} />
                                        <Bar dataKey="value" fill="#4caf50" />
                                      </RechartsBarChart>
                                    </ResponsiveContainer>
                                  </Paper>
                                </Grid>
                              )}
                              
                              {topLosers.length > 0 && (
                                <Grid item xs={12} md={6}>
                                  <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                                    <Typography variant="subtitle1" style={{ color: '#f44336', marginBottom: '12px', fontWeight: 'bold' }}>
                                      跌幅榜图表
                                    </Typography>
                                    <ResponsiveContainer width="100%" height={300}>
                                      <RechartsBarChart
                                        data={topLosers.slice(0, 10).map((loser) => {
                                          let symbol = '', changePercent = 0;
                                          if (typeof loser === 'string') {
                                            const match = loser.match(/(\d{6})[^\d]*([+-]?\d+\.?\d*%)/);
                                            if (match) {
                                              symbol = match[1];
                                              changePercent = parseFloat(match[2]) || 0;
                                            }
                                          } else if (typeof loser === 'object') {
                                            symbol = loser.symbol || '';
                                            changePercent = parseFloat(loser.change_percent || loser.loss || '0') || 0;
                                          }
                                          return { name: symbol, value: Math.abs(changePercent) };
                                        })}
                                      >
                                        <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                                        <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} tick={{ fill: '#aaa', fontSize: 10 }} />
                                        <YAxis tick={{ fill: '#aaa' }} />
                                        <Tooltip contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #f44336' }} labelStyle={{ color: '#f44336' }} formatter={(value) => `-${value}%`} />
                                        <Bar dataKey="value" fill="#f44336" />
                                      </RechartsBarChart>
                                    </ResponsiveContainer>
                                  </Paper>
                                </Grid>
                              )}
                            </Grid>
                          </Box>
                        )}
                        

                        {/* Stocks Table */}
                        {stocks.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              股票列表 ({stocks.length})
                            </Typography>
                            <TableContainer style={{ maxHeight: '600px', overflow: 'auto' }}>
                              <Table size="small" stickyHeader>
                                <TableHead>
                                  <TableRow style={{ backgroundColor: '#1a1a2e' }}>
                                    <TableCell style={{ color: '#bb86fc' }}>代码</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>名称</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>价格</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>涨跌</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>涨跌幅</TableCell>
                                    <TableCell style={{ color: '#bb86fc' }}>成交量</TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {stocks.map((stock, stockIndex) => (
                                    <TableRow key={stockIndex}>
                                      <TableCell style={{ color: '#4caf50', fontFamily: 'monospace' }}>
                                        {stock.symbol}
                                      </TableCell>
                                      <TableCell>{stock.name || 'N/A'}</TableCell>
                                      <TableCell>{stock.price || 'N/A'}</TableCell>
                                      <TableCell
                                        style={{
                                          color: stock.change && (typeof stock.change === 'string' ? stock.change.includes('-') : parseFloat(stock.change) < 0) ? '#f44336' : '#4caf50'
                                        }}
                                      >
                                        {stock.change || 'N/A'}
                                      </TableCell>
                                      <TableCell
                                        style={{
                                          color: stock.change_percent && (typeof stock.change_percent === 'string' ? stock.change_percent.includes('-') : parseFloat(stock.change_percent) < 0) ? '#f44336' : '#4caf50'
                                        }}
                                      >
                                        {stock.change_percent || 'N/A'}
                                      </TableCell>
                                      <TableCell>{stock.volume || 'N/A'}</TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </TableContainer>
                          </Box>
                        )}


                        {/* Show raw data preview if AI processing failed */}
                        {hasError && siteData?.raw_data_preview && (
                          <Box mt={2}>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              原始数据预览 (前500字符):
                            </Typography>
                            <Paper style={{ padding: '12px', backgroundColor: '#1a1a2e', maxHeight: '300px', overflow: 'auto' }}>
                              <Typography variant="body2" style={{ 
                                fontFamily: 'monospace', 
                                fontSize: '12px', 
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                                color: '#4caf50'
                              }}>
                                {siteData.raw_data_preview}
                              </Typography>
                            </Paper>
                          </Box>
                        )}
                      </Paper>
                    </Grid>
                  );
                  });
                })()}
              </Grid>
            )}
          </DialogContent>
          <DialogActions style={{ backgroundColor: '#1a1a2e', padding: '16px' }}>
            <Button onClick={handleCloseModal} style={{ color: '#bb86fc' }}>
              关闭
            </Button>
          </DialogActions>
        </Dialog>

        {/* JSON Data Modal */}
        <Dialog
          open={jsonModalOpen}
          onClose={handleCloseJsonModal}
          maxWidth="lg"
          fullWidth
          PaperProps={{
            style: {
              backgroundColor: '#1e1e1e',
              color: '#ffffff',
              maxHeight: '90vh'
            }
          }}
        >
          <DialogTitle style={{ backgroundColor: '#1a1a2e', color: '#bb86fc' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="h5">JSON 数据详情</Typography>
              <IconButton onClick={handleCloseJsonModal} style={{ color: '#bb86fc' }}>
                <CloseIcon />
              </IconButton>
            </Box>
          </DialogTitle>
          <DialogContent style={{ backgroundColor: '#252526', paddingTop: '20px' }}>
            {jsonData && (
              <Box>
                <Paper
                  style={{
                    backgroundColor: '#1e1e1e',
                    padding: '16px',
                    overflow: 'auto',
                    maxHeight: '70vh'
                  }}
                >
                  <pre style={{
                    color: '#4caf50',
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, monospace',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}>
                    {JSON.stringify(jsonData, null, 2)}
                  </pre>
                </Paper>
                <Box mt={2}>
                  <Typography variant="caption" color="textSecondary">
                    提示: 您可以复制此 JSON 数据用于分析或调试
                  </Typography>
                </Box>
              </Box>
            )}
          </DialogContent>
          <DialogActions style={{ backgroundColor: '#1a1a2e', padding: '16px' }}>
            <Button
              onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(jsonData, null, 2));
                alert('JSON 数据已复制到剪贴板！');
              }}
              style={{ color: '#4caf50', borderColor: '#4caf50' }}
              variant="outlined"
            >
              复制 JSON
            </Button>
            <Button onClick={handleCloseJsonModal} style={{ color: '#bb86fc' }}>
              关闭
            </Button>
          </DialogActions>
        </Dialog>
      </div>
    </ThemeProvider>
  );
}

export default App;