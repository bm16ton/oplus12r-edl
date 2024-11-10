IDIR =./
CC=gcc
CFLAGS=-I$(IDIR)
BINDIR=bin
ODIR=obj
LDIR =lib

LIBS=-lrt

DEPS = fh_comdef.h fh_loader_sha.h

OBJ = fh_loader_sha.o fh_loader.o


$(ODIR)/%.o: %.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

fh_loader: $(OBJ)
	mkdir -p $(BINDIR)
	$(CC) -o bin/$@ $^ $(CFLAGS) $(LIBS)

.PHONY: clean

clean:
	rm -f $(ODIR)/*.o
	rm -f $(BINDIR)/*.o
