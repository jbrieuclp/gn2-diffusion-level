// Angular core
import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import {HttpModule, Http} from '@angular/http';
import { FormsModule } from '@angular/forms';

// For Angular Dependencies
import 'hammerjs';
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';
import { MaterialModule, MdIconModule, MdNativeDateModule } from '@angular/material';
import { FlexLayoutModule } from '@angular/flex-layout';
import { CarouselModule } from 'ngx-bootstrap/carousel';
import { ChartModule } from 'angular2-chartjs';
import {TranslateModule, TranslateLoader} from '@ngx-translate/core';
import {TranslateHttpLoader} from '@ngx-translate/http-loader';
import { ToastrModule } from 'ngx-toastr';

// Angular created component
import { AppComponent } from './app.component';
import { AppRoutingModule } from './routing/app-routing.module'; // RoutingModule
import { AccueilComponent } from './apps/accueil/accueil.component';
import { ContactFauneComponent } from './apps/contact-faune/contact-faune.component';
import { ContactFloreComponent } from './apps/contact-flore/contact-flore.component';
import { SidenavItemsComponent } from './components/sidenav-items/sidenav-items.component';
import { PageNotFoundComponent } from './components/page-not-found/page-not-found.component';

// Service
import { MapService } from './services/map.service';
import { NavService } from './services/nav.service';
import { MapComponent } from './components/map/map.component';
import { SigninComponent } from './components/auth/signin/signin.component';
import { AuthService } from './components/auth/auth.service';
import { AuthGuard } from './components/auth/auth-guard.service';
import { CfauneFormComponent } from './apps/contact-faune/cfaune-form/cfaune-form.component';
// AoT requires an exported function for factories
export function HttpLoaderFactory(http: Http) {
    return new TranslateHttpLoader(http, './assets/i18n/', '.json');
}
@NgModule({
  declarations: [
    AppComponent,
    AccueilComponent,
    ContactFauneComponent,
    ContactFloreComponent,
    SidenavItemsComponent,
    PageNotFoundComponent,
    MapComponent,
    SigninComponent,
    CfauneFormComponent
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpModule,
    BrowserAnimationsModule,
    MaterialModule,
    FlexLayoutModule,
    AppRoutingModule,
    MdIconModule,
    CarouselModule.forRoot(),
    MdNativeDateModule,
    ChartModule,
    TranslateModule.forRoot({
            loader: {
                provide: TranslateLoader,
                useFactory: HttpLoaderFactory,
                deps: [Http]
            }
        }),
    ToastrModule.forRoot()
  ],
  providers: [NavService, MapService, AuthService, AuthGuard],
  bootstrap: [AppComponent]
})
export class AppModule { }
