import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Fraude } from '../models/fraude.model';

@Injectable({
  providedIn: 'root'
})
export class FraudeService {

  private API = 'http://localhost:8000';

  constructor(private http: HttpClient) {}

  getTopFraudes(): Observable<Fraude[]> {
    return this.http.get<Fraude[]>(`${this.API}/fraudes/top`);
  }
  getFraudes(): Observable<Fraude[]> {
    return this.http.get<Fraude[]>(`${this.API}/fraudes`);
  }
}