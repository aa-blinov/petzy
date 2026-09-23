import api from './api';

export interface PushSubscribeInput {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  timezone: string;
}

export const pushService = {
  async getVapidPublicKey(): Promise<string> {
    const response = await api.get<{ public_key: string }>('/push/vapid-public-key');
    return response.data.public_key;
  },

  async subscribe(data: PushSubscribeInput): Promise<void> {
    await api.post('/push/subscribe', data);
  },

  async unsubscribe(endpoint: string): Promise<void> {
    await api.post('/push/unsubscribe', { endpoint });
  },
};
