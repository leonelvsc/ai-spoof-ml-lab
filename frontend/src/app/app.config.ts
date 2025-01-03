import {ApplicationConfig, provideZoneChangeDetection} from '@angular/core';

// import {routes} from './app.routes';
import {initializeApp, provideFirebaseApp} from '@angular/fire/app';
import {getAuth, provideAuth} from '@angular/fire/auth';
import {getFirestore, provideFirestore} from '@angular/fire/firestore';
import {getStorage, provideStorage} from '@angular/fire/storage';
import {provideAnimationsAsync} from '@angular/platform-browser/animations/async';
import {getAnalytics, provideAnalytics} from '@angular/fire/analytics';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({eventCoalescing: true}),
    provideFirebaseApp(() => initializeApp({
      "projectId": "your_project",
      "appId": "your_id",
      "storageBucket": "your_project.firebasestorage.app",
      "apiKey": "your_api_key",
      "authDomain": "your_project.firebaseapp.com",
      "messagingSenderId": "some_id",
      "measurementId": "some_id"
    })),
    provideAuth(() => getAuth()),
    provideFirestore(() => getFirestore()),
    provideStorage(() => getStorage()),
    provideAnalytics(() => getAnalytics()),
    provideAnimationsAsync()
  ]
};
