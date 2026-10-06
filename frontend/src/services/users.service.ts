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

/** The whole account list, as a shape. The list itself is paged and admin-only: admin.service.getUsers.
 *  Nothing should read it as «every account» — one page is not the list, and the person edited on the user
 *  form used to be looked up in it, so anyone past the first page was «не найден». */
export interface UserResponse {
  user: User;
}

/** The subset of a user visible to a co-owner they share a pet with —
 *  no email, no is_active, unlike the admin-only `User` above. */
export interface UserPublicProfile {
  username: string;
  full_name?: string | null;
  created_at: string;
  shared_pets: string[];
}

export const usersService = {
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

  /** The server's own words about what it did, plus the account when it was sent back. */
  async updateUser(username: string, data: UserUpdate): Promise<{ message: string; user?: User }> {
    const response = await api.put<{ message: string; user?: User }>(`/users/${username}`, data);
    return response.data;
  },

  async deleteUser(username: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/users/${username}`);
    return response.data;
  },

  async getPublicProfile(username: string): Promise<UserPublicProfile> {
    const response = await api.get<UserPublicProfile>(`/users/${username}/profile`);
    return response.data;
  },
};

