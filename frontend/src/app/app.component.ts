import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {AudioService, FileTask} from './services/audio.service';
import {AsyncPipe, JsonPipe} from '@angular/common';
import {
  MatExpansionModule
} from '@angular/material/expansion';
import {MatButton} from '@angular/material/button';
import {MatTableModule} from '@angular/material/table';
import {MatGridList, MatGridTile} from '@angular/material/grid-list';
import {MatProgressBar} from '@angular/material/progress-bar';
import {Analytics, logEvent} from '@angular/fire/analytics';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    MatTableModule,
    MatExpansionModule,
    FormsModule,
    AsyncPipe,
    JsonPipe,
    MatButton,
    MatGridList,
    MatGridTile,
    MatProgressBar
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent {
  currentTasks = signal<FileTask[]>([]);
  audioService = inject(AudioService);
  analytics = inject(Analytics);

  async processFiles(element: HTMLInputElement) {
    logEvent(this.analytics, 'analyze');

    this.currentTasks.set(
      await this.audioService.uploadFiles(element)
    );
  }
}
