/**
 * Formats API errors into human-readable messages.
 * Handles string details, Pydantic 422 validation error arrays, and object errors.
 * Never produces "[object Object]".
 */

export interface ParsedApiError {
  message: string;
  fieldErrors: Record<string, string>;
  rawErrors: string[];
}

const FIELD_LABEL_MAP: Record<string, string> = {
  scheduled_start: 'Voting start',
  start_datetime: 'Voting start',
  scheduled_end: 'Voting end',
  end_datetime: 'Voting end',
  election_id: 'Election',
  timezone: 'Timezone',
  trustees: 'Trustee roster',
  name: 'Name',
  email: 'Email',
  title: 'Election title',
  candidates: 'Candidates',
  password: 'Password',
  admin_password: 'Admin password',
  username: 'Username',
};

export function formatApiError(error: any): ParsedApiError {
  if (!error) {
    return {
      message: 'Something went wrong. Please try again.',
      fieldErrors: {},
      rawErrors: [],
    };
  }

  // If error is already a string
  if (typeof error === 'string') {
    return {
      message: error,
      fieldErrors: {},
      rawErrors: [error],
    };
  }

  const detail = error.detail !== undefined ? error.detail : error.message;

  // Case 1: detail is a simple string
  if (typeof detail === 'string') {
    return {
      message: detail,
      fieldErrors: {},
      rawErrors: [detail],
    };
  }

  // Case 2: detail is a FastAPI/Pydantic validation error array
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    const messages: string[] = [];

    for (const item of detail) {
      if (typeof item === 'string') {
        messages.push(item);
        continue;
      }

      if (typeof item === 'object' && item !== null) {
        // Extract location path, e.g. ['body', 'scheduled_start'] -> 'scheduled_start'
        const loc = Array.isArray(item.loc) ? item.loc : [];
        const lastField = loc.length > 0 ? String(loc[loc.length - 1]) : '';
        const fieldKey = loc.filter((p: any) => p !== 'body').join('.');

        let rawMsg = typeof item.msg === 'string' ? item.msg : 'Invalid value';
        // Clean up common Pydantic prefix phrases
        rawMsg = rawMsg.replace(/^Value error,\s*/i, '');
        rawMsg = rawMsg.charAt(0).toUpperCase() + rawMsg.slice(1);

        const fieldLabel = FIELD_LABEL_MAP[lastField] || (lastField ? lastField.replace(/_/g, ' ') : '');

        if (fieldLabel) {
          const fullMsg = `${fieldLabel}: ${rawMsg}`;
          messages.push(fullMsg);
          if (lastField) {
            fieldErrors[lastField] = rawMsg;
          }
          if (fieldKey) {
            fieldErrors[fieldKey] = rawMsg;
          }
        } else {
          messages.push(rawMsg);
        }
      }
    }

    const combined = messages.length > 0 ? messages.join('. ') : 'Validation failed. Please check the form fields.';
    return {
      message: combined,
      fieldErrors,
      rawErrors: messages,
    };
  }

  // Case 3: detail is an object with message or error
  if (typeof detail === 'object' && detail !== null) {
    const msg = detail.message || detail.error || detail.detail;
    if (typeof msg === 'string') {
      return {
        message: msg,
        fieldErrors: {},
        rawErrors: [msg],
      };
    }
  }

  return {
    message: 'Something went wrong. Please try again.',
    fieldErrors: {},
    rawErrors: [],
  };
}
