import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../lib/api';
import { initSocket, disconnectSocket } from '../lib/socket';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    if (token && savedUser) {
      setUser(JSON.parse(savedUser));
      initSocket(JSON.parse(savedUser).id);
    }

    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const response = await authApi.login({ email, password });
    const { access_token, user: userData } = response.data;

    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));

    setUser(userData);
    initSocket(userData.id);

    return userData;
  };

  const register = async (email, password, full_name) => {
    const response = await authApi.register({ email, password, full_name });
    const { access_token, user: userData } = response.data;

    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));

    setUser(userData);
    initSocket(userData.id);

    return userData;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    disconnectSocket();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
