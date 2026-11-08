export const passwordHint='Use at least 8 characters, including an uppercase letter, lowercase letter, number and special character.';
export function validPassword(value:string):boolean{return Array.from(value).length>=8&&Array.from(value).length<=1024&&/\p{Lu}/u.test(value)&&/\p{Ll}/u.test(value)&&/[0-9]/.test(value)&&/[^\p{L}\p{N}\s]/u.test(value);}
