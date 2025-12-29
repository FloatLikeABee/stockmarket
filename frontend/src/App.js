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
  CardContent
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
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
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
  const [currentView, setCurrentView] = useState('overview'); // 'overview', 'charts', 'browser'
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonData, setJsonData] = useState(null);

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

  // Trigger crawl
  const triggerCrawl = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/crawl`, {
        sites: null, // Crawl all sites
        category: "manual"
      });
      // Refresh data after crawl - wait longer for background task to complete
      setTimeout(() => {
        fetchLatestData();
        fetchStats();
      }, 10000); // Wait 10 seconds for crawl to complete
    } catch (error) {
      console.error('触发爬取时出错:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatestData();
    fetchStats();
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
            <Button color="inherit" onClick={triggerCrawl} startIcon={<RefreshIcon />}>
              立即爬取
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
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary">日期时间</Typography>
                        <Typography variant="body1">
                          {new Date(selectedRecord.timestamp).toLocaleString()}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary">类别</Typography>
                        <Chip
                          label={selectedRecord.metadata?.category || 'unknown'}
                          color={selectedRecord.metadata?.category === 'manual' ? 'secondary' : 'primary'}
                        />
                      </Grid>
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary">数据源</Typography>
                        <Typography variant="body1">
                          {selectedRecord.metadata?.sites_crawled?.join(', ') || 'N/A'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Grid>

                {/* Stock Data by Site */}
                {selectedRecord.data && Object.keys(selectedRecord.data).map((site, siteIndex) => {
                  const siteData = selectedRecord.data[site];
                  
                  // Debug: Log the siteData structure
                  console.log(`[Debug] Site: ${site}, siteData:`, siteData);
                  console.log(`[Debug] ai_processed_data:`, siteData?.ai_processed_data);
                  
                  // Handle null or undefined siteData
                  if (!siteData) {
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
                  
                  // Check for errors first
                  if (siteData.error) {
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
                  
                  // Handle ai_processed_data - it might be a string or object
                  let processedData = siteData?.ai_processed_data;
                  if (typeof processedData === 'string') {
                    // Try to parse if it's a JSON string
                    try {
                      processedData = JSON.parse(processedData);
                    } catch (e) {
                      console.warn(`[Debug] Failed to parse ai_processed_data as JSON for ${site}:`, e);
                      processedData = null;
                    }
                  }
                  
                  // Extract data from processedData
                  const stocks = processedData?.stocks || [];
                  const indices = processedData?.indices || [];
                  const topGainers = processedData?.top_gainers || [];
                  const topLosers = processedData?.top_losers || [];
                  const marketOverview = processedData?.market_overview || 'N/A';
                  const tradingSummary = processedData?.trading_summary || '';
                  const news = processedData?.news || [];
                  const hasError = siteData?.error || (!processedData && siteData?.raw_data_preview);
                  
                  // Debug: Log extracted data
                  console.log(`[Debug] Extracted for ${site}:`, {
                    stocks: stocks.length,
                    indices: indices.length,
                    topGainers: topGainers.length,
                    topLosers: topLosers.length,
                    hasMarketOverview: !!marketOverview,
                    hasTradingSummary: !!tradingSummary,
                    news: news.length,
                    processedData: processedData
                  });
                  
                  // Show message if no data found but processedData exists
                  if (!hasError && processedData && stocks.length === 0 && indices.length === 0 && topGainers.length === 0 && 
                      topLosers.length === 0 && marketOverview === 'N/A' && !tradingSummary && news.length === 0) {
                    return (
                      <Grid item xs={12} key={siteIndex}>
                        <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e', border: '1px solid #ff9800' }}>
                          <Typography variant="h6" style={{ color: '#ff9800', marginBottom: '12px' }}>
                            {site} - 数据结构异常
                          </Typography>
                          <Typography variant="body2" style={{ color: '#ff9800', marginBottom: '8px' }}>
                            AI处理数据存在但格式不符合预期。显示原始处理数据:
                          </Typography>
                          <Box mt={2}>
                            <Paper style={{ padding: '12px', backgroundColor: '#1a1a2e', maxHeight: '400px', overflow: 'auto' }}>
                              <Typography variant="body2" style={{ fontFamily: 'monospace', fontSize: '12px', whiteSpace: 'pre-wrap', color: '#4caf50' }}>
                                {JSON.stringify(processedData, null, 2)}
                              </Typography>
                            </Paper>
                          </Box>
                        </Paper>
                      </Grid>
                    );
                  }

                  return (
                    <Grid item xs={12} key={siteIndex}>
                      <Paper style={{ padding: '16px', backgroundColor: '#2a2a3e' }}>
                        <Typography variant="h6" style={{ color: '#4caf50', marginBottom: '12px' }}>
                          {site} 数据
                        </Typography>

                        {/* Show warning if AI processing failed but raw data exists */}
                        {hasError && (
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

                        {/* Top Gainers */}
                        {topGainers.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              涨幅榜 ({topGainers.length})
                            </Typography>
                            <List>
                              {topGainers.map((gainer, idx) => {
                                // Handle both string and object formats
                                const displayText = typeof gainer === 'string' 
                                  ? gainer 
                                  : (gainer.symbol || gainer.name || JSON.stringify(gainer));
                                const gainValue = typeof gainer === 'object' ? gainer.gain || gainer.change_percent || '' : '';
                                
                                return (
                                  <ListItem key={idx} style={{ paddingLeft: 0 }}>
                                    <Typography variant="body2" style={{ color: '#4caf50' }}>
                                      • {displayText} {gainValue && `(${gainValue})`}
                                    </Typography>
                                  </ListItem>
                                );
                              })}
                            </List>
                          </Box>
                        )}

                        {/* Top Losers */}
                        {topLosers.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              跌幅榜 ({topLosers.length})
                            </Typography>
                            <List>
                              {topLosers.map((loser, idx) => {
                                // Handle both string and object formats
                                const displayText = typeof loser === 'string' 
                                  ? loser 
                                  : (loser.symbol || loser.name || JSON.stringify(loser));
                                const lossValue = typeof loser === 'object' ? loser.loss || loser.change_percent || '' : '';
                                
                                return (
                                  <ListItem key={idx} style={{ paddingLeft: 0 }}>
                                    <Typography variant="body2" style={{ color: '#f44336' }}>
                                      • {displayText} {lossValue && `(${lossValue})`}
                                    </Typography>
                                  </ListItem>
                                );
                              })}
                            </List>
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
                                          color: stock.change && stock.change.includes('-') ? '#f44336' : '#4caf50'
                                        }}
                                      >
                                        {stock.change || 'N/A'}
                                      </TableCell>
                                      <TableCell
                                        style={{
                                          color: stock.change_percent && stock.change_percent.includes('-') ? '#f44336' : '#4caf50'
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

                        {/* News */}
                        {news.length > 0 && (
                          <Box>
                            <Typography variant="subtitle2" color="textSecondary" style={{ marginBottom: '8px' }}>
                              相关新闻 ({news.length})
                            </Typography>
                            <Box style={{ maxHeight: '300px', overflow: 'auto' }}>
                              <List>
                                {news.map((newsItem, newsIndex) => {
                                  // Handle both string and object formats
                                  const displayText = typeof newsItem === 'string' 
                                    ? newsItem 
                                    : (newsItem.title || newsItem.text || JSON.stringify(newsItem));
                                  
                                  return (
                                    <ListItem key={newsIndex} style={{ paddingLeft: 0 }}>
                                      <Typography variant="body2">• {displayText}</Typography>
                                    </ListItem>
                                  );
                                })}
                              </List>
                            </Box>
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
                })}
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