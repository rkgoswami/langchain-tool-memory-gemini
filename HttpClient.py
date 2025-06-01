import requests
import logging

class HttpClient:
    def __init__(self):
        self.default_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def get(self, url, headers=None):
        """
        Perform a GET request.
        :param url: The URL to send the GET request to.
        :param headers: Optional headers to include in the request.
        :return: JSON response.
        """
        merged_headers = {**self.default_headers, **(headers or {})}
        print(f"GET Request Headers: {merged_headers}")  # Debugging line
        response = requests.get(url, headers=merged_headers, verify=False)
        response.raise_for_status()
        return response.json()

    def post(self, url, data=None, headers=None):
        """
        Perform a POST request.
        :param url: The URL to send the POST request to.
        :param data: The data to include in the POST request.
        :param headers: Optional headers to include in the request.
        :return: JSON response.
        """
        merged_headers = {**self.default_headers, **(headers or {})}
        response = requests.post(url, json=data, headers=merged_headers)
        response.raise_for_status()
        return response.json()

    def request(self, method, url, data=None, headers=None):
        """
        Perform a request based on the method (GET or POST).
        :param method: The HTTP method ('GET' or 'POST').
        :param url: The URL to send the request to.
        :param data: The data to include in the request (for POST).
        :param headers: Optional headers to include in the request.
        :return: JSON response.
        """
        merged_headers = {**self.default_headers, **(headers or {})}
        if method.upper() == 'GET':
            return self.get(url, headers=merged_headers)
        elif method.upper() == 'POST':
            return self.post(url, data=data, headers=merged_headers)
        else:
            raise ValueError("Unsupported HTTP method: " + method)

# Exportable for use in other files
__all__ = ['HttpClient']