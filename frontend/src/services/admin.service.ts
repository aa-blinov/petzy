import api from './api';
import type { User } from './users.service';

/** One page of the account list, and how many the search found in all. */
export interface UserListPage {
  users: User[];
  total: number;
  page: number;
  per_page: number;
}

export interface UserListParams {
  page?: number;
  /** What to look for in a login or a name. Empty means the whole list. */
  query?: string;
}

/** How many people one page of the admin list holds. */
export const ADMIN_USERS_PER_PAGE = 20;

/** The admin panel's account list.
 *
 *  Admin only, and only here: this call runs whatever is typed into `query`
 *  over every account in the app, which is why it has no counterpart in the
 *  co-owner's account lookup (users.service.searchUsers, which is narrowed
 *  to the caller's own circle and a whole login typed in full).
 */
export const adminService = {
  async getUsers({ page = 1, query = '' }: UserListParams = {}): Promise<UserListPage> {
    const response = await api.get<UserListPage>('/users', {
      params: { page, q: query.trim() },
    });
    return response.data;
  },
};