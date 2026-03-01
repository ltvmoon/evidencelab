import React from 'react';
import { USER_MODULE } from '../../config';
import { useAuth } from '../../hooks/useAuth';
import GroupManager from './GroupManager';
import UserManager from './UserManager';

interface AdminPanelProps {
  isActive: boolean;
  availableDatasources: string[];
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isActive, availableDatasources }) => {
  const { user } = useAuth();
  if (!USER_MODULE || !isActive || !user?.is_superuser) return null;
  return (
    <div className="admin-panel">
      <h2>Administration</h2>
      <UserManager />
      <GroupManager availableDatasources={availableDatasources} />
    </div>
  );
};

export default AdminPanel;
