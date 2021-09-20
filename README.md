# CS-50-Flask
Stock market traiding simulator.

Tocken prices gathered from iexcloud.io/cloud API.
Before start your API key is need to be registered in order to be able to query IEX’s data. To do so, follow these steps:

1) Visit iexcloud.io/cloud-login#/register/.
2) Select the “Individual” account type, then enter your email address and a password, and click “Create account”.
3) Once registered, scroll down to “Get started for free” and click “Select Start” to choose the free plan.
4) Once you’ve confirmed your account via a confirmation email, visit https://iexcloud.io/console/tokens.
5) Copy the key that appears under the Token column (it should begin with pk_).
In a terminal window , execute:
$ export API_KEY=value
where value is that (pasted) value, without any space immediately before or after the =.
