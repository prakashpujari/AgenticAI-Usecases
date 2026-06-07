# Deployment Checklist - Secure Token Management

## 🔒 Step 1: Revoke Exposed Credentials (DO THIS FIRST!)

Your `.env` file is exposed in git. These tokens must be revoked:

### Revoke OpenAI Token
1. Go to: https://platform.openai.com/api-keys
2. Find key starting with `sk-proj-h34ST5`
3. Click the ⚠️ and **Delete**
4. Generate **NEW** key

### Revoke Pinecone Token
1. Go to: https://console.pinecone.io
2. Account → API Keys
3. Find key starting with `pcsk_9VCYW`
4. Click **Delete**
5. Generate **NEW** key

### Revoke Jira Token
1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Find token starting with `ATATT3xFfGF0`
3. Click **Revoke**
4. Generate **NEW** token

### Revoke LangSmith API Key
1. Go to: https://smith.langchain.com/settings
2. Find key starting with `lsv2_pt_04b2`
3. Click **Delete**
4. Generate **NEW** key

---

## 🎯 Step 2: Generate New Tokens

After revoking all old tokens, generate NEW ones:

### New OpenAI API Key
```
Site: https://platform.openai.com/api-keys
Action: Create new secret key
Copy: The full key starting with sk-proj-
```

### New Pinecone API Key
```
Site: https://console.pinecone.io (API Keys tab)
Action: Create API Key
Copy: The full key starting with pcsk_
```

### New Jira API Token
```
Site: https://id.atlassian.com/manage-profile/security/api-tokens
Action: Create API token
Copy: The full token
```

### New LangSmith API Key
```
Site: https://smith.langchain.com/settings
Action: Create API Key
Copy: The full key starting with lsv2_
```

### New Vercel Token (for deployment)
```
Site: https://vercel.com/account/tokens
Action: Create new token (check "Full Access" for initial setup)
Copy: The full token starting with vcp_
```

### New Render API Key (for deployment)
```
Site: https://dashboard.render.com
Account → API Keys → Create API Key
Copy: The full key starting with rnd_
```

---

## 📝 Step 3: Prepare Credentials

Once you have all NEW tokens, you have two options:

### Option A: Provide Tokens to Me (Faster)
Share the new tokens here and I'll:
1. Update Vercel & Render dashboards
2. Deploy both applications
3. Test everything end-to-end
4. Document the URLs

### Option B: Manual Deployment (More Control)
I'll guide you through:
1. Setting env vars in Vercel dashboard
2. Setting env vars in Render dashboard  
3. Manually triggering deployments
4. Verifying production URLs

---

## ⚠️ Important Notes

- **NEVER** commit `.env` to git (should be in `.gitignore`)
- **NEVER** share credentials in Slack/email/chat again
- **ALWAYS** use platform dashboards or environment variable management
- **ROTATE** tokens quarterly or if exposed

---

## Ready to Proceed?

Once you've:
- [x] Revoked all old tokens (OpenAI, Pinecone, Jira, LangSmith)
- [x] Generated NEW tokens
- [x] Generated Vercel & Render deployment credentials

**Reply with:**
```
1. New Vercel token (vcp_...)
2. New Render API key (rnd_...)
3. New OpenAI API key (sk-proj-...)
4. New Pinecone API key (pcsk_...)
5. New Jira API token (ATATT...)
6. New LangSmith API key (lsv2_...)
```

Or let me know you want to handle it manually and I'll guide you through the Vercel/Render dashboards.

