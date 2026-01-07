import api from './api';

export interface User {
  _id: string;
  username: string;
  full_name?: string;
  email?: string;
  created_at?: string;
  created_by?: string;
  is_active?: boolean;
}

export interface UserCreate {
  username: string;
  password: string;
  full_name?: string;
  email?: string;
}

export interface UserUpdate {
  full_name?: string;
  email?: string;
  is_active?: boolean;
}

export interface UserPasswordReset {
  new_password: string;
}

export interface UserListResponse {
  users: User[];
}

export interface UserResponse {
  user: User;
}

export const usersService = {
  async getUsers(): Promise<User[]> {
    const response = await api.get<UserListResponse>('/users');
    return response.data.users;
  },

  async searchUsers(query: string): Promise<{ username: string }[]> {
    const response = await api.get<{ users: { username: string }[] }>(`/users/search?q=${encodeURIComponent(query)}`);
    return response.data.users;
  },

  async getUser(username: string): Promise<User> {
    const response = await api.get<UserResponse>(`/users/${username}`);
    return response.data.user;
  },

  async createUser(data: UserCreate): Promise<User> {
    const response = await api.post<{ message: string; user: User }>('/users', data);
    return response.data.user;
  },

  async updateUser(username: string, data: UserUpdate): Promise<User> {
    const response = await api.put<{ message: string; user: User }>(`/users/${username}`, data);
    return response.data.user;
  },

  async deleteUser(username: string): Promise<void> {
    await api.delete(`/users/${username}`);
  },

  async resetPassword(username: string, newPassword: string): Promise<void> {
    await api.post(`/users/${username}/reset-password`, { new_password: newPassword });
  }
};

