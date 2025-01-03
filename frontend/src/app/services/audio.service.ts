import {inject, Injectable, signal, WritableSignal} from '@angular/core';
import {deleteDoc, doc, Firestore, onSnapshot} from '@angular/fire/firestore';
import {deleteObject, ref, Storage, uploadBytesResumable} from '@angular/fire/storage';
import {Auth, signInAnonymously} from '@angular/fire/auth';
import {BehaviorSubject, Subject} from 'rxjs';

export type FileTask = {
  name: string,
  uuid: string,
  task: any,
  progress: Subject<string>,
  progress_numeric: Subject<number>,
  data: WritableSignal<any>
};

@Injectable({
  providedIn: 'root'
})
export class AudioService {

  private readonly firestore = inject(Firestore);
  private readonly fileStorage = inject(Storage);
  private readonly auth = inject(Auth);

  constructor() {
  }

  async uploadFiles(input: HTMLInputElement): Promise<FileTask[]> {
    await signInAnonymously(this.auth);

    if (!input.files) {
      return [];
    }

    const files: FileList = input.files;
    const fileTasks: FileTask[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files.item(i);

      if(['audio/mpeg', 'audio/x-m4a', 'audio/mp4', 'audio/mp3'].includes(file!.type)) {
        continue;
      }

      if (file) {
        const uuid = self.crypto.randomUUID();
        const storageRef = ref(this.fileStorage, uuid);
        const task = uploadBytesResumable(storageRef, file);

        const fileTask: FileTask = {
          name: file.name,
          uuid: uuid,
          task,
          progress: new Subject<string>(),
          progress_numeric: new BehaviorSubject<number>(0),
          data: signal<any>(undefined)
        };

        const docRef = doc(this.firestore, 'audio_predictions', fileTask.uuid);
        const unsubscribe = onSnapshot(docRef, {
          next: snapshot => {
            const data = snapshot.data();

            if (!data) {
              return;
            }

            fileTask.data.set(data);
            fileTask.progress.next('Complete')
            unsubscribe();
            deleteDoc(docRef);
            deleteObject(storageRef);
          }
        });

        fileTasks.push(fileTask);

        task.on('state_changed',
          (snapshot) => {

            const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
            fileTask.progress.next(`Uploading ${progress.toFixed(2).toString()}%`);
            fileTask.progress_numeric.next(progress);
          },
          () => {
            fileTask.progress_numeric.next(100);
            fileTask.progress.next('Failed to upload');
          },
          () => {
            fileTask.progress_numeric.next(100);
            fileTask.progress.next('Analyzing...');
          }
        );
      }
    }

    return fileTasks;
  }
}
