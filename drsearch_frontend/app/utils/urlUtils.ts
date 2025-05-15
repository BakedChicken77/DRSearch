// app\utils\urlUtils.ts

export function convertToHttpUrlIfNeeded(uncPath: string): string {
    const pattern = /drs\.com@ssl\\DavWWWRoot/;
    
    if (pattern.test(uncPath)) {
      // Replace the initial part of the UNC path
      let httpUrl = uncPath.replace(/^\\\\home\.drs\.com@ssl\\DavWWWRoot/, 'https://home.drs.com');
      
      // Replace backslashes with forward slashes
      httpUrl = httpUrl.replace(/\\/g, '/');
      
      // URL-encode the path
      httpUrl = encodeURI(httpUrl);
      
      // Append the query parameter
      httpUrl += '?web=1';
  
      return httpUrl;
    } else {
      // Return the original path if it doesn't match the pattern
      return uncPath;
    }
  }