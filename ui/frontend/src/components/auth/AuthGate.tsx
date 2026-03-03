import React from 'react';
import { USER_MODULE_MODE } from '../../config';
import { useAuth } from '../../hooks/useAuth';
import LoginModal from './LoginModal';

/**
 * When USER_MODULE_MODE is "on_active", blocks all content behind a
 * non-dismissable login modal until the user authenticates.
 */
export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();

  if (USER_MODULE_MODE === 'on_active' && !isLoading && !user) {
    return <LoginModal onClose={() => {}} required />;
  }

  return <>{children}</>;
};
