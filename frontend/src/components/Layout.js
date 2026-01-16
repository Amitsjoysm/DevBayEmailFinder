import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { Button } from './ui/button';
import {
  Zap, LayoutDashboard, ShieldCheck, Search, Settings, BarChart3, LogOut, Moon, Sun, Menu
} from 'lucide-react';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/verifier', icon: ShieldCheck, label: 'Verifier' },
    { path: '/finder', icon: Search, label: 'Finder' },
    { path: '/analytics', icon: BarChart3, label: 'Analytics' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const Sidebar = () => (
    <div className="flex flex-col h-full">
      <div className="flex items-center space-x-2 px-6 py-4 border-b border-border/50">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
          <Zap className="w-6 h-6 text-white" strokeWidth={1.5} />
        </div>
        <span className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>VerifyMail</span>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={`flex items-center space-x-3 px-4 py-3 rounded-md transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`}
            >
              <Icon className="w-5 h-5" strokeWidth={1.5} />
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border/50">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-muted-foreground">Theme</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            data-testid="theme-toggle-button"
            className="w-9 h-9 p-0"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>

        <div className="flex items-center space-x-3 px-4 py-3 bg-secondary/50 rounded-md mb-2">
          <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-bold">
            {user?.email?.[0]?.toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user?.full_name || 'User'}</div>
            <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          </div>
        </div>

        <Button
          variant="ghost"
          onClick={handleLogout}
          data-testid="logout-button"
          className="w-full justify-start text-red-500 hover:text-red-600 hover:bg-red-500/10"
        >
          <LogOut className="w-4 h-4 mr-2" strokeWidth={1.5} />
          Logout
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="hidden lg:flex">
        <aside className="w-64 bg-surface border-r border-border/50 fixed left-0 top-0 bottom-0 z-40">
          <Sidebar />
        </aside>
        <main className="flex-1 ml-64">
          <div className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border/50">
            <div className="px-6 py-4">
              <h1 className="text-2xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>
                {navItems.find(item => item.path === location.pathname)?.label || 'VerifyMail'}
              </h1>
            </div>
          </div>
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>

      <div className="lg:hidden">
        <div className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border/50">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" strokeWidth={1.5} />
              </div>
              <span className="text-lg font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>VerifyMail</span>
            </div>
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="sm" data-testid="mobile-menu-button">
                  <Menu className="w-5 h-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0">
                <Sidebar />
              </SheetContent>
            </Sheet>
          </div>
        </div>
        <main className="p-4">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
